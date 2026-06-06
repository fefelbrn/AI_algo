"""Secret and environment-variable loading — never hard-code credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class IBKRSecrets:
    host: str
    port: int
    client_id: int


def load_secrets(
    *,
    env_file: Path | None = None,
    defaults: IBKRSecrets | None = None,
) -> IBKRSecrets:
    """Load IBKR connection settings from environment variables.

    Precedence: env vars > .env file > defaults from config YAML.
    """
    if env_file is None:
        env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    base = defaults or IBKRSecrets(host="127.0.0.1", port=4002, client_id=10)

    host = os.getenv("IBKR_HOST", base.host)
    port = int(os.getenv("IBKR_PORT", str(base.port)))
    client_id = int(os.getenv("IBKR_CLIENT_ID", str(base.client_id)))

    return IBKRSecrets(host=host, port=port, client_id=client_id)
