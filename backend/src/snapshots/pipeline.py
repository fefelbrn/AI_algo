"""Snapshot build pipeline — raw parquet → market_state_snapshots parquet."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.collectors.models import iso_ts
from src.paths import backend_root
from src.snapshots.builder import build_snapshots_from_rows
from src.snapshots.config import SnapshotBuilderConfig, load_snapshot_config
from src.snapshots.reader import read_raw_for_session
from src.storage.layers import DataLayer
from src.storage.platform import StoragePlatform

logger = logging.getLogger(__name__)


@dataclass
class SnapshotBuildSummary:
    trade_date: str
    session_id: str | None
    input_event_count: int
    output_row_count: int
    output_path: Path | None
    source_partitions: list[str] = field(default_factory=list)
    completeness: dict[str, Any] = field(default_factory=dict)


def run_snapshot_pipeline(
    artifacts_dir: Path,
    trade_date: str,
    *,
    session_id: str | None = None,
    config_dir: Path | None = None,
) -> SnapshotBuildSummary:
    config_dir = config_dir or backend_root() / "configs"
    snap_cfg = load_snapshot_config(config_dir)
    platform = StoragePlatform.open(artifacts_dir, config_dir)

    raw_rows, source_paths = read_raw_for_session(artifacts_dir, trade_date, session_id)
    if not raw_rows:
        logger.warning("No raw events for dt=%s session=%s", trade_date, session_id)
        return SnapshotBuildSummary(
            trade_date=trade_date,
            session_id=session_id,
            input_event_count=0,
            output_row_count=0,
            output_path=None,
            source_partitions=source_paths,
        )

    snapshots = build_snapshots_from_rows(raw_rows, snap_cfg)
    run_id = f"snapshot_build_{iso_ts().replace(':', '').replace('+00:00', 'Z')}"
    platform.metadata.start_job(
        run_id,
        "snapshot_builder",
        code_version=snap_cfg.version,
        config_hashes={"snapshots": snap_cfg.config_hash, "storage": platform.config.config_hash},
        input_partitions={"raw_market_events": f"dt={trade_date}"},
        started_at=iso_ts(),
    )

    rows = [s.to_row() for s in snapshots]
    sid = session_id or (snapshots[0].session_id if snapshots else "unknown")
    source_key = f"dt={trade_date}/session_id={sid}"

    output_path, _ = platform.write_parquet_partition(
        DataLayer.MARKET_STATE_SNAPSHOTS,
        rows,
        trade_date=trade_date,
        filename="snapshots.parquet",
        run_id=run_id,
        session_id=sid,
        source_layers=[(DataLayer.RAW_MARKET_EVENTS.value, source_key)],
        version_id=f"snap_{snap_cfg.config_hash}_{sid}",
    )

    completeness = _completeness_metrics(snapshots)
    platform.metadata.complete_job(
        run_id,
        status="success",
        completed_at=iso_ts(),
        output_partitions={DataLayer.MARKET_STATE_SNAPSHOTS.value: f"dt={trade_date}/session_id={sid}"},
    )
    platform.write_manifest(
        output_path.parent,
        {
            "job": "snapshot_builder",
            "trade_date": trade_date,
            "session_id": sid,
            "input_events": len(raw_rows),
            "output_rows": len(snapshots),
            "source_partitions": source_paths,
            "completeness": completeness,
            "config_hash": snap_cfg.config_hash,
        },
    )

    logger.info(
        "Built %d snapshot rows from %d raw events → %s",
        len(snapshots),
        len(raw_rows),
        output_path,
    )

    return SnapshotBuildSummary(
        trade_date=trade_date,
        session_id=sid,
        input_event_count=len(raw_rows),
        output_row_count=len(snapshots),
        output_path=output_path,
        source_partitions=source_paths,
        completeness=completeness,
    )


def _completeness_metrics(snapshots: list) -> dict[str, Any]:
    if not snapshots:
        return {}
    total = len(snapshots)
    with_ref = sum(1 for s in snapshots if s.reference_price is not None)
    stale = sum(1 for s in snapshots if s.flag_stale)
    fallback = sum(1 for s in snapshots if s.flag_fallback)
    by_role: dict[str, int] = {}
    for s in snapshots:
        by_role[s.role] = by_role.get(s.role, 0) + 1
    return {
        "total_rows": total,
        "reference_coverage_ratio": with_ref / total,
        "stale_ratio": stale / total,
        "fallback_ratio": fallback / total,
        "rows_by_role": by_role,
    }
