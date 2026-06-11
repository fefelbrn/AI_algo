"""Snapshot builder configuration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.connectivity.config import _load_yaml


@dataclass(frozen=True)
class RoleThresholds:
    max_quote_age_seconds: float
    max_spread_pct: float


@dataclass(frozen=True)
class SnapshotBuilderConfig:
    version: str
    thresholds: dict[str, RoleThresholds]
    reference_priority: tuple[str, ...]
    allow_carry_forward: bool
    storage_subdir: str
    config_hash: str


def load_snapshot_config(config_dir: Path) -> SnapshotBuilderConfig:
    path = config_dir / "snapshots.yaml"
    raw = _load_yaml(path)
    builder = raw.get("builder", {})
    ages = builder.get("max_quote_age_seconds", {})
    spreads = builder.get("max_spread_pct", {})
    roles = set(ages.keys()) | set(spreads.keys()) | {"index", "future", "option"}

    thresholds = {
        role: RoleThresholds(
            max_quote_age_seconds=float(ages.get(role, 300)),
            max_spread_pct=float(spreads.get(role, 5.0)),
        )
        for role in roles
    }

    return SnapshotBuilderConfig(
        version=raw.get("version", "snapshots_v0.0.0"),
        thresholds=thresholds,
        reference_priority=tuple(raw.get("reference_priority", ["mid", "last", "carry_forward"])),
        allow_carry_forward=bool(builder.get("allow_carry_forward", True)),
        storage_subdir=raw.get("storage", {}).get("subdir", "market_state_snapshots"),
        config_hash=hashlib.sha256(path.read_bytes()).hexdigest()[:12],
    )
