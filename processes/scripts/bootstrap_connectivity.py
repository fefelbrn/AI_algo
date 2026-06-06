#!/usr/bin/env python3
"""Step 1 bootstrap — prove end-to-end IBKR connectivity without placing orders.

Acceptance criteria (roadmap Step 1):
  - Session state printed
  - Current time shown
  - One underlying contract resolved
  - One market-data retrieval
  - One JSON line written to disk
  - Health checks green (or actionable warnings)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

from _paths import BACKEND_ROOT, REPO_ROOT, setup_import_path

setup_import_path()

from src.connectivity.adapter import IBKRAdapter
from src.connectivity.config import ibkr_secrets_from_config, load_config
from src.connectivity.health import run_health_checks
from src.connectivity.secrets import load_secrets


def _setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"bootstrap_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def _write_bootstrap_artifact(
    artifacts_dir: Path,
    *,
    subdir: str,
    payload: dict,
) -> Path:
    out_dir = artifacts_dir / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"bootstrap_{ts}.jsonl"
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IBKR connectivity bootstrap (Step 1)")
    parser.add_argument(
        "--config",
        type=Path,
        default=BACKEND_ROOT / "configs" / "dev.yaml",
        help="Path to environment config YAML",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config, repo_root_path=REPO_ROOT)
    _setup_logging(config.paths.logs_dir)

    logger = logging.getLogger("bootstrap")
    now_utc = dt.datetime.now(dt.timezone.utc)
    logger.info("Bootstrap started at %s", now_utc.isoformat())

    secrets = load_secrets(
        env_file=REPO_ROOT / ".env",
        defaults=ibkr_secrets_from_config(config),
    )
    adapter = IBKRAdapter(secrets, config)

    try:
        adapter.connect()
        session = adapter.session_state()
        logger.info("Session state: %s", session)

        contract = adapter.resolve_contract(
            symbol=config.bootstrap.smoke_underlying,
            exchange=config.bootstrap.smoke_exchange,
            currency=config.bootstrap.smoke_currency,
        )
        logger.info("Resolved contract: %s (conId=%s)", contract.local_symbol, contract.con_id)

        quote = adapter.request_quote(contract)
        logger.info(
            "Quote for %s — bid=%s ask=%s last=%s",
            quote.symbol,
            quote.bid,
            quote.ask,
            quote.last,
        )

        health = run_health_checks(adapter.ib, config)
        for check in health.checks:
            logger.info("Health [%s] %s: %s", check.status.upper(), check.name, check.message)

        payload = {
            "step": 1,
            "run_type": "bootstrap_connectivity",
            "timestamp_utc": now_utc.isoformat(),
            "environment": config.environment,
            "session": {
                "connected": session.connected,
                "host": session.host,
                "port": session.port,
                "client_id": session.client_id,
                "accounts": list(session.accounts),
                "server_version": session.server_version,
            },
            "contract": {
                "symbol": contract.symbol,
                "exchange": contract.exchange,
                "currency": contract.currency,
                "con_id": contract.con_id,
                "local_symbol": contract.local_symbol,
            },
            "quote": {
                "bid": quote.bid,
                "ask": quote.ask,
                "last": quote.last,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "volume": quote.volume,
            },
            "health": {
                "overall_status": health.overall_status,
                "checks": [
                    {
                        "name": c.name,
                        "status": c.status,
                        "message": c.message,
                        "details": c.details,
                    }
                    for c in health.checks
                ],
            },
        }

        artifact_path = _write_bootstrap_artifact(
            config.paths.artifacts_dir,
            subdir=config.bootstrap.output_subdir,
            payload=payload,
        )
        logger.info("Artifact written: %s", artifact_path)

        if health.overall_status == "fail":
            logger.error("Bootstrap completed with FAILING health checks")
            return 1
        if health.overall_status == "warn":
            logger.warning("Bootstrap completed with warnings (market may be closed)")
            return 0
        logger.info("Bootstrap SUCCESS — all health checks passed")
        return 0

    except ConnectionRefusedError:
        logger.error(
            "Connection refused at %s:%s — is IB Gateway or TWS running?",
            secrets.host,
            secrets.port,
        )
        return 1
    except Exception:
        logger.exception("Bootstrap failed")
        return 1
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
