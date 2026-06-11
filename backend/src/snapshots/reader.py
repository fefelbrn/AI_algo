"""Read raw market event partitions for replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.storage.layers import DataLayer


def list_raw_partitions(artifacts_dir: Path, trade_date: str) -> list[Path]:
    base = artifacts_dir / DataLayer.RAW_MARKET_EVENTS.value / f"dt={trade_date}"
    if not base.exists():
        return []
    return sorted(base.glob("session_id=*/events_part_*.parquet"))


def read_raw_events(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        table = pq.ParquetFile(path).read()
        for row in table.to_pylist():
            row["_source_partition"] = str(path.parent)
            rows.append(row)
    return rows


def read_raw_for_session(
    artifacts_dir: Path,
    trade_date: str,
    session_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if session_id:
        pattern = artifacts_dir / DataLayer.RAW_MARKET_EVENTS.value / f"dt={trade_date}" / f"session_id={session_id}"
        paths = sorted(pattern.glob("events_part_*.parquet"))
    else:
        paths = list_raw_partitions(artifacts_dir, trade_date)
    return read_raw_events(paths), [str(p) for p in paths]
