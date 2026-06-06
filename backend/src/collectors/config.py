"""Collector configuration loader."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.connectivity.config import _load_yaml


@dataclass(frozen=True)
class TenorBucket:
    label: str
    days: int


@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    fallback: "ContractSpec | None" = None


@dataclass(frozen=True)
class ProductConfig:
    name: str
    description: str
    index: ContractSpec
    futures: ContractSpec
    options: ContractSpec


@dataclass(frozen=True)
class OptionsSubsetConfig:
    moneyness_bands: tuple[float, ...]
    include_calls: bool
    include_puts: bool
    max_expiries_per_tenor: int


@dataclass(frozen=True)
class SnapshotConfig:
    interval_seconds: int
    quote_wait_seconds: float
    max_duration_seconds: int | None


@dataclass(frozen=True)
class CollectorStorageConfig:
    subdir: str
    flush_every_snapshots: int


@dataclass(frozen=True)
class CollectorConfig:
    version: str
    snapshot: SnapshotConfig
    storage: CollectorStorageConfig
    tenors: tuple[TenorBucket, ...]
    options_subset: OptionsSubsetConfig
    products: tuple[ProductConfig, ...]
    config_hash: str


def _parse_contract(raw: dict[str, Any]) -> ContractSpec:
    fb = raw.get("fallback")
    return ContractSpec(
        symbol=raw["symbol"],
        sec_type=raw.get("sec_type", "STK"),
        exchange=raw.get("exchange", "SMART"),
        currency=raw.get("currency", "USD"),
        fallback=_parse_contract(fb) if fb else None,
    )


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def load_collector_config(config_dir: Path) -> CollectorConfig:
    path = config_dir / "collector.yaml"
    raw = _load_yaml(path)
    snap = raw.get("snapshot", {})
    stor = raw.get("storage", {})
    opt = raw.get("options_subset", {})

    tenors = tuple(
        TenorBucket(label=t["label"], days=int(t["days"]))
        for t in raw.get("tenors", [])
    )
    products = tuple(
        ProductConfig(
            name=p["name"],
            description=p.get("description", ""),
            index=_parse_contract(p["index"]),
            futures=_parse_contract(p["futures"]),
            options=_parse_contract(p["options"]),
        )
        for p in raw.get("products", [])
    )

    return CollectorConfig(
        version=raw.get("version", "collector_v0.0.0"),
        snapshot=SnapshotConfig(
            interval_seconds=int(snap.get("interval_seconds", 300)),
            quote_wait_seconds=float(snap.get("quote_wait_seconds", 2.0)),
            max_duration_seconds=snap.get("max_duration_seconds"),
        ),
        storage=CollectorStorageConfig(
            subdir=stor.get("subdir", "raw_market_events"),
            flush_every_snapshots=int(stor.get("flush_every_snapshots", 1)),
        ),
        tenors=tenors,
        options_subset=OptionsSubsetConfig(
            moneyness_bands=tuple(opt.get("moneyness_bands", [0.90, 1.00, 1.10])),
            include_calls=bool(opt.get("include_calls", True)),
            include_puts=bool(opt.get("include_puts", True)),
            max_expiries_per_tenor=int(opt.get("max_expiries_per_tenor", 1)),
        ),
        products=products,
        config_hash=_hash(path),
    )
