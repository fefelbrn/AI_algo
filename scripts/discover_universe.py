#!/usr/bin/env python3
"""Step 2 — discover and persist the canonical instrument master."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.connectivity.adapter import IBKRAdapter
from src.connectivity.config import ibkr_secrets_from_config, load_config
from src.connectivity.secrets import load_secrets
from src.universe.master import InstrumentMaster


def _setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"discover_universe_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover IBKR option universe (Step 2)")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "dev.yaml",
        help="Environment config YAML",
    )
    parser.add_argument(
        "--session-date",
        type=str,
        default=None,
        help="Session date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=2,
        help="IBKR client id for universe service (default: 2)",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config, project_root=PROJECT_ROOT)
    _setup_logging(config.paths.logs_dir)
    logger = logging.getLogger("discover_universe")

    session_date = (
        dt.date.fromisoformat(args.session_date) if args.session_date else dt.date.today()
    )
    secrets = load_secrets(defaults=ibkr_secrets_from_config(config))
    secrets = type(secrets)(host=secrets.host, port=secrets.port, client_id=args.client_id)

    master = InstrumentMaster.from_config(config.config_dir, config.paths.artifacts_dir)
    adapter = IBKRAdapter(secrets, config)

    try:
        adapter.connect()
        logger.info("Connected — discovering universe for %s", session_date.isoformat())
        snapshot = master.discover_and_persist(session_date=session_date, adapter=adapter)

        summary = {
            "as_of_date": snapshot.as_of_date,
            "universe_version": snapshot.universe_version,
            "underlying_count": len(snapshot.underlyings),
            "option_count": len(snapshot.options),
            "qc_summary": snapshot.qc_summary,
            "underlyings": [u.symbol for u in snapshot.underlyings],
        }
        logger.info("Discovery complete:\n%s", json.dumps(summary, indent=2))

        if snapshot.qc_summary.get("overall_status") == "fail":
            return 1
        return 0
    except ConnectionRefusedError:
        logger.error(
            "Connection refused at %s:%s — is IB Gateway running?",
            secrets.host,
            secrets.port,
        )
        return 1
    except Exception:
        logger.exception("Universe discovery failed")
        return 1
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
