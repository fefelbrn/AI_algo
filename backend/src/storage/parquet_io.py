"""Unified Parquet read/write with validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.storage.config import StorageConfig
from src.storage.layers import DataLayer
from src.storage.schemas import PLATFORM_SCHEMA_VERSION, schema_for_layer
from src.storage.validation import stamp_schema_version, validate_rows


class ParquetLayerWriter:
    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._part_counters: dict[str, int] = {}

    def write_rows(
        self,
        layer: DataLayer,
        rows: list[dict[str, Any]],
        path: Path,
    ) -> int:
        stamped = stamp_schema_version(rows)
        validate_rows(layer, stamped, self._config)
        schema = schema_for_layer(layer)
        table = pa.Table.from_pylist(stamped).cast(schema)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            table,
            path,
            compression="snappy",
            use_dictionary=False,
        )
        return len(rows)

    def next_part_path(self, directory: Path, prefix: str = "part") -> Path:
        key = str(directory)
        idx = self._part_counters.get(key, 0)
        self._part_counters[key] = idx + 1
        return directory / f"{prefix}_{idx:04d}.parquet"

    def read_partition(self, path: Path, *, layer: DataLayer) -> pa.Table:
        if path.is_dir():
            table = pq.read_table(path)
        else:
            table = pq.ParquetFile(path).read()
        expected = schema_for_layer(layer)
        if table.schema != expected:
            table = table.cast(expected)
        return table


def rows_from_table(table: pa.Table) -> list[dict[str, Any]]:
    return table.to_pylist()
