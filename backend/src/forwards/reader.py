"""Read market-state snapshot partitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.storage.layers import DataLayer


def list_snapshot_partitions(
    artifacts_dir: Path,
    trade_date: str,
    session_id: str | None = None,
) -> list[Path]:
    base = artifacts_dir / DataLayer.MARKET_STATE_SNAPSHOTS.value / f"dt={trade_date}"
    if not base.exists():
        return []
    if session_id:
        path = base / f"session_id={session_id}" / "snapshots.parquet"
        return [path] if path.exists() else []
    return sorted(base.glob("session_id=*/snapshots.parquet"))


def read_snapshot_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        table = pq.ParquetFile(path).read()
        for row in table.to_pylist():
            row["_source_partition"] = str(path.parent)
            rows.append(row)
    return rows
