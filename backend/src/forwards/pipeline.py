"""Forward build pipeline — snapshots → forward_curve + diagnostics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.collectors.models import iso_ts
from src.forwards.config import load_forward_config
from src.forwards.engine import build_forward_curve
from src.forwards.reader import list_snapshot_partitions, read_snapshot_rows
from src.paths import backend_root
from src.storage.layers import DataLayer
from src.storage.platform import StoragePlatform

logger = logging.getLogger(__name__)


@dataclass
class ForwardBuildSummary:
    trade_date: str
    session_id: str | None
    input_snapshot_rows: int
    forward_count: int
    diagnostic_count: int
    forward_path: Path | None
    diagnostics_path: Path | None
    by_product: dict[str, int] = field(default_factory=dict)


def run_forward_pipeline(
    artifacts_dir: Path,
    trade_date: str,
    *,
    session_id: str | None = None,
    config_dir: Path | None = None,
) -> ForwardBuildSummary:
    config_dir = config_dir or backend_root() / "configs"
    fwd_cfg = load_forward_config(config_dir)
    platform = StoragePlatform.open(artifacts_dir, config_dir)

    paths = list_snapshot_partitions(artifacts_dir, trade_date, session_id)
    rows = read_snapshot_rows(paths)
    if not rows:
        logger.warning("No market-state snapshots for dt=%s", trade_date)
        return ForwardBuildSummary(
            trade_date=trade_date,
            session_id=session_id,
            input_snapshot_rows=0,
            forward_count=0,
            diagnostic_count=0,
            forward_path=None,
            diagnostics_path=None,
        )

    curves, diagnostics = build_forward_curve(rows, fwd_cfg)
    run_id = f"forward_build_{iso_ts().replace(':', '').replace('+00:00', 'Z')}"
    sid = session_id or rows[0].get("session_id", "unknown")
    source_key = f"dt={trade_date}/session_id={sid}"

    platform.metadata.start_job(
        run_id,
        "forward_engine",
        code_version=fwd_cfg.version,
        config_hashes={"forwards": fwd_cfg.config_hash},
        input_partitions={DataLayer.MARKET_STATE_SNAPSHOTS.value: source_key},
        started_at=iso_ts(),
    )

    forward_path = None
    diagnostics_path = None

    if curves:
        forward_path, _ = platform.write_parquet_partition(
            DataLayer.FORWARD_CURVE,
            [c.to_row() for c in curves],
            trade_date=trade_date,
            filename="forwards.parquet",
            run_id=run_id,
            session_id=sid,
            product=None,
            source_layers=[(DataLayer.MARKET_STATE_SNAPSHOTS.value, source_key)],
            version_id=f"fwd_{fwd_cfg.config_hash}_{sid}",
        )

    if diagnostics:
        diagnostics_path, _ = platform.write_parquet_partition(
            DataLayer.FORWARD_DIAGNOSTICS,
            [d.to_row() for d in diagnostics],
            trade_date=trade_date,
            filename="forward_diagnostics.parquet",
            run_id=run_id,
            session_id=sid,
            source_layers=[(DataLayer.MARKET_STATE_SNAPSHOTS.value, source_key)],
            version_id=f"fwd_diag_{fwd_cfg.config_hash}_{sid}",
        )

    by_product: dict[str, int] = {}
    for c in curves:
        by_product[c.product_name] = by_product.get(c.product_name, 0) + 1

    platform.metadata.complete_job(
        run_id,
        status="success",
        completed_at=iso_ts(),
        output_partitions={
            DataLayer.FORWARD_CURVE.value: f"dt={trade_date}/session_id={sid}",
            DataLayer.FORWARD_DIAGNOSTICS.value: f"dt={trade_date}/session_id={sid}",
        },
    )

    if forward_path:
        platform.write_manifest(
            forward_path.parent,
            {
                "job": "forward_engine",
                "trade_date": trade_date,
                "session_id": sid,
                "forward_count": len(curves),
                "diagnostic_count": len(diagnostics),
                "by_product": by_product,
                "config_hash": fwd_cfg.config_hash,
                "risk_free_rate": fwd_cfg.risk_free_rate,
            },
        )

    logger.info("Built %d forwards, %d diagnostics", len(curves), len(diagnostics))

    return ForwardBuildSummary(
        trade_date=trade_date,
        session_id=sid,
        input_snapshot_rows=len(rows),
        forward_count=len(curves),
        diagnostic_count=len(diagnostics),
        forward_path=forward_path,
        diagnostics_path=diagnostics_path,
        by_product=by_product,
    )
