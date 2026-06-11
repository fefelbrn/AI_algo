"""Forward engine configuration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.connectivity.config import _load_yaml
from src.collectors.config import TenorBucket, load_collector_config


@dataclass(frozen=True)
class ForwardEngineConfig:
    version: str
    risk_free_rate: float
    day_count: float
    min_parity_candidates: int
    min_candidates_after_qc: int
    mad_z_threshold: float
    max_parity_residual_pct: float
    prefer_future_when_available: bool
    blend_future_parity: bool
    use_inverse_spread: bool
    min_option_mid: float
    tenors: tuple[TenorBucket, ...]
    config_hash: str


def load_forward_config(config_dir: Path) -> ForwardEngineConfig:
    path = config_dir / "forwards.yaml"
    raw = _load_yaml(path)
    pricing = raw.get("pricing", {})
    engine = raw.get("engine", {})
    weights = raw.get("weights", {})
    collector_cfg = load_collector_config(config_dir)

    return ForwardEngineConfig(
        version=raw.get("version", "forwards_v0.0.0"),
        risk_free_rate=float(pricing.get("risk_free_rate", 0.0)),
        day_count=float(pricing.get("day_count", 365.0)),
        min_parity_candidates=int(engine.get("min_parity_candidates", 1)),
        min_candidates_after_qc=int(engine.get("min_candidates_after_qc", 1)),
        mad_z_threshold=float(engine.get("mad_z_threshold", 3.5)),
        max_parity_residual_pct=float(engine.get("max_parity_residual_pct", 5.0)),
        prefer_future_when_available=bool(engine.get("prefer_future_when_available", True)),
        blend_future_parity=bool(engine.get("blend_future_parity", False)),
        use_inverse_spread=bool(weights.get("use_inverse_spread", True)),
        min_option_mid=float(weights.get("min_option_mid", 0.01)),
        tenors=collector_cfg.tenors,
        config_hash=hashlib.sha256(path.read_bytes()).hexdigest()[:12],
    )
