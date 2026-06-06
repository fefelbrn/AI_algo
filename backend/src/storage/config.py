"""Storage layer configuration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.connectivity.config import _load_yaml


@dataclass(frozen=True)
class MetadataConfig:
    db_subdir: str
    db_filename: str


@dataclass(frozen=True)
class PartitioningConfig:
    date_key: str
    session_key: str
    underlying_key: str
    product_key: str


@dataclass(frozen=True)
class RetentionPolicy:
    tier: int
    retain_days: int
    description: str = ""


@dataclass(frozen=True)
class SchemaEvolutionConfig:
    allow_extra_columns: bool
    reject_unknown_layers: bool


@dataclass(frozen=True)
class StorageConfig:
    version: str
    schema_version: str
    metadata: MetadataConfig
    partitioning: PartitioningConfig
    retention: dict[str, RetentionPolicy]
    schema_evolution: SchemaEvolutionConfig
    config_hash: str


def load_storage_config(config_dir: Path) -> StorageConfig:
    path = config_dir / "storage.yaml"
    raw = _load_yaml(path)
    meta = raw.get("metadata", {})
    part = raw.get("partitioning", {})
    evo = raw.get("schema_evolution", {})

    retention: dict[str, RetentionPolicy] = {}
    for layer, pol in raw.get("retention", {}).items():
        retention[layer] = RetentionPolicy(
            tier=int(pol.get("tier", 2)),
            retain_days=int(pol.get("retain_days", 365)),
            description=pol.get("description", ""),
        )

    return StorageConfig(
        version=raw.get("version", "storage_v0.0.0"),
        schema_version=raw.get("schema_version", "1.0.0"),
        metadata=MetadataConfig(
            db_subdir=meta.get("db_subdir", "metadata"),
            db_filename=meta.get("db_filename", "platform.db"),
        ),
        partitioning=PartitioningConfig(
            date_key=part.get("date_key", "dt"),
            session_key=part.get("session_key", "session_id"),
            underlying_key=part.get("underlying_key", "underlying"),
            product_key=part.get("product_key", "product"),
        ),
        retention=retention,
        schema_evolution=SchemaEvolutionConfig(
            allow_extra_columns=bool(evo.get("allow_extra_columns", False)),
            reject_unknown_layers=bool(evo.get("reject_unknown_layers", True)),
        ),
        config_hash=hashlib.sha256(path.read_bytes()).hexdigest()[:12],
    )
