"""Unit tests for Step 1 config loading — no IBKR connection required."""

from pathlib import Path

from src.connectivity.config import load_config
from src.connectivity.secrets import load_secrets


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_dev_config():
    config = load_config(PROJECT_ROOT / "configs" / "dev.yaml", project_root=PROJECT_ROOT)
    assert config.environment == "dev"
    assert config.ibkr.port == 4002
    assert config.bootstrap.smoke_underlying == "SPY"


def test_load_secrets_defaults():
    secrets = load_secrets(defaults=None)
    assert secrets.host == "127.0.0.1"
    assert secrets.port == 4002
    assert secrets.client_id == 10
