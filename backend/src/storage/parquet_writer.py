"""Append-only Parquet writer for raw market events — uses StoragePlatform."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.collectors.models import RawMarketEvent
from src.storage.layers import DataLayer
from src.storage.platform import StoragePlatform
from src.storage.schemas import RAW_MARKET_EVENTS_SCHEMA

# Re-export for backward compatibility
EVENT_SCHEMA = RAW_MARKET_EVENTS_SCHEMA


class ParquetEventWriter:
    """Writes snapshot batches to partitioned Parquet via the storage platform."""

    def __init__(
        self,
        platform: StoragePlatform,
        *,
        session_id: str,
        trade_date: str,
        run_id: str,
    ) -> None:
        self._platform = platform
        self._session_id = session_id
        self._trade_date = trade_date
        self._run_id = run_id
        self._part = 0
        self.total_events = 0
        self.total_snapshots = 0
        self._output_dir = platform.partitions.layer_dir(
            DataLayer.RAW_MARKET_EVENTS,
            trade_date,
            session_id=session_id,
        )

    @classmethod
    def from_artifacts(
        cls,
        artifacts_dir: Path,
        *,
        subdir: str,
        session_id: str,
        trade_date: str,
        run_id: str | None = None,
    ) -> "ParquetEventWriter":
        platform = StoragePlatform.open(artifacts_dir)
        return cls(
            platform,
            session_id=session_id,
            trade_date=trade_date,
            run_id=run_id or session_id,
        )

    def write_events(self, events: list[RawMarketEvent]) -> Path | None:
        if not events:
            return None
        rows = [e.to_row() for e in events]
        filename = f"events_part_{self._part:04d}.parquet"
        path, _ = self._platform.write_parquet_partition(
            DataLayer.RAW_MARKET_EVENTS,
            rows,
            trade_date=self._trade_date,
            filename=filename,
            run_id=self._run_id,
            session_id=self._session_id,
            version_id=f"v1_{self._run_id}_part{self._part:04d}",
        )
        self._part += 1
        self.total_events += len(events)
        self.total_snapshots += 1
        return path

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def platform(self) -> StoragePlatform:
        return self._platform


def write_session_manifest(
    output_dir: Path,
    manifest: dict[str, Any],
    *,
    platform: StoragePlatform | None = None,
) -> Path:
    if platform is not None:
        return platform.write_manifest(output_dir, manifest)
    path = output_dir / "session_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return path
