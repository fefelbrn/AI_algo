"""Snapshot-based raw market data collector — Step 3."""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.collectors.config import CollectorConfig, load_collector_config
from src.collectors.models import RawMarketEvent, iso_ts, utc_now
from src.collectors.normalize import ticker_to_events
from src.collectors.universe_builder import build_subscription_universe
from src.connectivity.adapter import IBKRAdapter
from src.paths import backend_root
from src.storage.parquet_writer import ParquetEventWriter, write_session_manifest
from src.storage.platform import StoragePlatform

logger = logging.getLogger(__name__)


@dataclass
class CollectorSessionSummary:
    session_id: str
    trade_date: str
    snapshot_count: int
    event_count: int
    subscription_count: int
    output_dir: Path
    reconnect_count: int = 0
    missing_snapshots: int = 0
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class RawCollector:
    """Polls IBKR on a fixed interval and writes append-only Parquet events."""

    def __init__(
        self,
        adapter: IBKRAdapter,
        config: CollectorConfig,
        artifacts_dir: Path,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._artifacts_dir = artifacts_dir
        self._platform = StoragePlatform.open(artifacts_dir)
        self._session_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
        self._trade_date = dt.date.today().isoformat()
        self._run_id = f"collector_{self._session_id}"
        self._platform.metadata.start_job(
            self._run_id,
            "raw_collector",
            code_version=config.version,
            config_hashes={
                "collector": config.config_hash,
                "storage": self._platform.config.config_hash,
            },
            started_at=iso_ts(),
        )
        self._writer = ParquetEventWriter(
            self._platform,
            session_id=self._session_id,
            trade_date=self._trade_date,
            run_id=self._run_id,
        )
        self._subscriptions = []
        self._diagnostics: list[dict] = []
        self._reconnect_count = 0
        self._missing_snapshots = 0

    @classmethod
    def from_config_dir(
        cls,
        adapter: IBKRAdapter,
        artifacts_dir: Path,
        config_dir: Path | None = None,
    ) -> "RawCollector":
        cfg = load_collector_config(config_dir or backend_root() / "configs")
        return cls(adapter, cfg, artifacts_dir)

    def prepare_universe(self, *, session_date: dt.date | None = None) -> None:
        built = build_subscription_universe(
            self._adapter,
            self._config,
            session_date=session_date,
        )
        self._subscriptions = built.subscriptions
        self._diagnostics = built.diagnostics
        logger.info(
            "Subscription universe ready — %d contracts (%s)",
            len(self._subscriptions),
            ", ".join(
                f"{p.name}: {sum(1 for s in self._subscriptions if s.product_name == p.name)}"
                for p in self._config.products
            ),
        )
        for product, spot in built.reference_spots.items():
            logger.info("Reference spot %s = %.4f", product, spot)

    def run(self) -> CollectorSessionSummary:
        if not self._subscriptions:
            raise RuntimeError("Call prepare_universe() before run()")

        start = time.monotonic()
        max_duration = self._config.snapshot.max_duration_seconds
        interval = self._config.snapshot.interval_seconds
        snapshot_idx = 0

        logger.info(
            "Collector session %s started — interval=%ss, contracts=%d",
            self._session_id,
            interval,
            len(self._subscriptions),
        )

        try:
            while True:
                if max_duration is not None and (time.monotonic() - start) >= max_duration:
                    logger.info("Max duration reached (%ss)", max_duration)
                    break

                loop_start = time.monotonic()
                snapshot_ts = utc_now()
                events = self._collect_snapshot(snapshot_ts)
                snapshot_idx += 1

                if events:
                    path = self._writer.write_events(events)
                    logger.info(
                        "Snapshot %d — %d events written to %s",
                        snapshot_idx,
                        len(events),
                        path,
                    )
                else:
                    self._missing_snapshots += 1
                    logger.warning("Snapshot %d — no events captured", snapshot_idx)

                elapsed = time.monotonic() - loop_start
                sleep_for = max(interval - elapsed, 0)
                if max_duration is not None and (time.monotonic() - start + sleep_for) >= max_duration:
                    break
                if sleep_for > 0:
                    time.sleep(sleep_for)

        except KeyboardInterrupt:
            logger.info("Collector interrupted by user")

        summary = CollectorSessionSummary(
            session_id=self._session_id,
            trade_date=self._trade_date,
            snapshot_count=self._writer.total_snapshots,
            event_count=self._writer.total_events,
            subscription_count=len(self._subscriptions),
            output_dir=self._writer.output_dir,
            reconnect_count=self._reconnect_count,
            missing_snapshots=self._missing_snapshots,
            diagnostics=self._diagnostics,
        )
        self._write_manifest(summary)
        return summary

    def _collect_snapshot(self, snapshot_ts: dt.datetime) -> list[RawMarketEvent]:
        if not self._adapter.ib.isConnected():
            logger.warning("IBKR disconnected — attempting reconnect")
            self._adapter.connect()
            self._reconnect_count += 1

        pairs = self._adapter.snapshot_subscriptions(
            self._subscriptions,
            wait_seconds=self._config.snapshot.quote_wait_seconds,
        )
        events: list[RawMarketEvent] = []
        for sub, ticker in pairs:
            events.extend(
                ticker_to_events(
                    sub,
                    ticker,
                    session_id=self._session_id,
                    snapshot_ts=snapshot_ts,
                )
            )
        return events

    def _write_manifest(self, summary: CollectorSessionSummary) -> None:
        manifest = {
            "session_id": summary.session_id,
            "trade_date": summary.trade_date,
            "collector_version": self._config.version,
            "config_hash": self._config.config_hash,
            "mode": "snapshot",
            "interval_seconds": self._config.snapshot.interval_seconds,
            "subscription_count": summary.subscription_count,
            "snapshot_count": summary.snapshot_count,
            "event_count": summary.event_count,
            "missing_snapshots": summary.missing_snapshots,
            "reconnect_count": summary.reconnect_count,
            "completed_at": iso_ts(),
            "universe_diagnostics": summary.diagnostics,
            "subscriptions": [
                {
                    "instrument_key": s.instrument_key,
                    "product_name": s.product_name,
                    "role": s.role,
                    "symbol": s.symbol,
                    "tenor_label": s.tenor_label,
                    "expiry": s.expiry,
                    "strike": s.strike,
                    "right": s.right,
                    "con_id": s.con_id,
                }
                for s in self._subscriptions
            ],
        }
        path = write_session_manifest(summary.output_dir, manifest, platform=self._platform)
        partition_key = f"dt={summary.trade_date}/session_id={summary.session_id}"
        self._platform.metadata.complete_job(
            self._run_id,
            status="success",
            completed_at=iso_ts(),
            output_partitions={
                "raw_market_events": partition_key,
            },
        )
        logger.info("Session manifest written: %s", path)
