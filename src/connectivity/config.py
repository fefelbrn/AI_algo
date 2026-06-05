"""Configuration loader — merges YAML configs with environment overrides."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.connectivity.secrets import IBKRSecrets


@dataclass(frozen=True)
class IBKRConfig:
    host: str
    port: int
    client_id: int
    timeout_seconds: int
    readonly: bool


@dataclass(frozen=True)
class PathsConfig:
    logs_dir: Path
    artifacts_dir: Path


@dataclass(frozen=True)
class HealthConfig:
    max_clock_skew_seconds: float
    heartbeat_interval_seconds: int


@dataclass(frozen=True)
class BootstrapConfig:
    smoke_underlying: str
    smoke_exchange: str
    smoke_currency: str
    output_subdir: str


@dataclass(frozen=True)
class AppConfig:
    environment: str
    ibkr: IBKRConfig
    paths: PathsConfig
    health: HealthConfig
    bootstrap: BootstrapConfig
    config_dir: Path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(
    config_path: Path | None = None,
    *,
    project_root: Path | None = None,
) -> AppConfig:
    root = project_root or Path(__file__).resolve().parents[2]
    config_path = config_path or root / "configs" / "dev.yaml"
    raw = _load_yaml(config_path)

    ibkr_raw = raw.get("ibkr", {})
    paths_raw = raw.get("paths", {})
    health_raw = raw.get("health", {})
    bootstrap_raw = raw.get("bootstrap", {})

    return AppConfig(
        environment=raw.get("environment", "dev"),
        ibkr=IBKRConfig(
            host=ibkr_raw.get("host", "127.0.0.1"),
            port=int(ibkr_raw.get("port", 4002)),
            client_id=int(ibkr_raw.get("client_id", 10)),
            timeout_seconds=int(ibkr_raw.get("timeout_seconds", 30)),
            readonly=bool(ibkr_raw.get("readonly", True)),
        ),
        paths=PathsConfig(
            logs_dir=root / paths_raw.get("logs_dir", "logs"),
            artifacts_dir=root / paths_raw.get("artifacts_dir", "artifacts"),
        ),
        health=HealthConfig(
            max_clock_skew_seconds=float(health_raw.get("max_clock_skew_seconds", 5.0)),
            heartbeat_interval_seconds=int(health_raw.get("heartbeat_interval_seconds", 10)),
        ),
        bootstrap=BootstrapConfig(
            smoke_underlying=bootstrap_raw.get("smoke_underlying", "SPY"),
            smoke_exchange=bootstrap_raw.get("smoke_exchange", "SMART"),
            smoke_currency=bootstrap_raw.get("smoke_currency", "USD"),
            output_subdir=bootstrap_raw.get("output_subdir", "bootstrap"),
        ),
        config_dir=config_path.parent,
    )


def ibkr_secrets_from_config(config: AppConfig) -> IBKRSecrets:
    return IBKRSecrets(
        host=config.ibkr.host,
        port=config.ibkr.port,
        client_id=config.ibkr.client_id,
    )
