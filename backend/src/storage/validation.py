"""Write-ahead validation — reject malformed records before persistence."""

from __future__ import annotations

from typing import Any

import pyarrow as pa

from src.storage.config import StorageConfig
from src.storage.layers import DataLayer
from src.storage.schemas import LAYER_SCHEMAS, PLATFORM_SCHEMA_VERSION, schema_for_layer


class ValidationError(Exception):
    def __init__(self, layer: DataLayer, message: str, context: dict[str, Any] | None = None) -> None:
        self.layer = layer
        self.context = context or {}
        super().__init__(f"[{layer.value}] {message}")


def stamp_schema_version(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        row.setdefault("schema_version", PLATFORM_SCHEMA_VERSION)
    return rows


def validate_rows(
    layer: DataLayer,
    rows: list[dict[str, Any]],
    config: StorageConfig,
) -> None:
    if not rows:
        return

    if config.schema_evolution.reject_unknown_layers and layer not in LAYER_SCHEMAS:
        raise ValidationError(layer, "Unknown data layer", {})

    schema = schema_for_layer(layer)
    required = set(schema.names)

    for i, row in enumerate(rows):
        missing = required - set(row.keys())
        if missing:
            raise ValidationError(
                layer,
                f"Row {i} missing required columns",
                {"missing": sorted(missing)},
            )
        extra = set(row.keys()) - required
        if extra and not config.schema_evolution.allow_extra_columns:
            raise ValidationError(
                layer,
                f"Row {i} has unexpected columns",
                {"extra": sorted(extra)},
            )

    table = pa.Table.from_pylist(rows)
    try:
        table.cast(schema)
    except pa.ArrowInvalid as exc:
        raise ValidationError(layer, f"Schema cast failed: {exc}", {}) from exc
