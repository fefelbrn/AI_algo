"""Universe discovery configuration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.connectivity.config import _load_yaml


@dataclass(frozen=True)
class DiscoveryConfig:
    min_maturity_days: int
    max_maturity_days: int
    max_contracts_per_underlying: int | None
    qualify_batch_size: int
    rights: tuple[str, ...]
    preferred_exchange: str | None


@dataclass(frozen=True)
class UniverseFilters:
    exchanges: tuple[str, ...]
    sec_types: tuple[str, ...]
    listing_status: str


@dataclass(frozen=True)
class UniverseStorageConfig:
    subdir: str


@dataclass(frozen=True)
class UnderlyingSeed:
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    description: str = ""


@dataclass(frozen=True)
class UniverseConfig:
    version: str
    discovery: DiscoveryConfig
    filters: UniverseFilters
    storage: UniverseStorageConfig
    underlyings: tuple[UnderlyingSeed, ...]
    config_hash: str


def _hash_configs(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def load_universe_config(
    config_dir: Path,
) -> UniverseConfig:
    universe_path = config_dir / "universe.yaml"
    instruments_path = config_dir / "instruments.yaml"
    universe_raw = _load_yaml(universe_path)
    instruments_raw = _load_yaml(instruments_path)

    disc = universe_raw.get("discovery", {})
    filt = universe_raw.get("filters", {})
    stor = universe_raw.get("storage", {})

    max_contracts = disc.get("max_contracts_per_underlying")
    seeds = tuple(
        UnderlyingSeed(
            symbol=u["symbol"],
            sec_type=u.get("sec_type", "STK"),
            exchange=u.get("exchange", "SMART"),
            currency=u.get("currency", "USD"),
            description=u.get("description", ""),
        )
        for u in instruments_raw.get("underlyings", [])
    )

    return UniverseConfig(
        version=universe_raw.get("version", "universe_v0.0.0"),
        discovery=DiscoveryConfig(
            min_maturity_days=int(disc.get("min_maturity_days", 1)),
            max_maturity_days=int(disc.get("max_maturity_days", 90)),
            max_contracts_per_underlying=int(max_contracts) if max_contracts else None,
            qualify_batch_size=int(disc.get("qualify_batch_size", 100)),
            rights=tuple(disc.get("rights", ["C", "P"])),
            preferred_exchange=disc.get("preferred_exchange"),
        ),
        filters=UniverseFilters(
            exchanges=tuple(filt.get("exchanges", [])),
            sec_types=tuple(filt.get("sec_types", ["STK"])),
            listing_status=filt.get("listing_status", "active"),
        ),
        storage=UniverseStorageConfig(subdir=stor.get("subdir", "instrument_master")),
        underlyings=seeds,
        config_hash=_hash_configs(universe_path, instruments_path),
    )
