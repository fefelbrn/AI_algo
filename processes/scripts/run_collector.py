#!/usr/bin/env python3
"""Step 3 — run snapshot collector (option C universe → Parquet)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

from _paths import BACKEND_ROOT, REPO_ROOT, setup_import_path

setup_import_path()

from src.collectors.collector import RawCollector
from src.connectivity.adapter import IBKRAdapter
from src.connectivity.config import ibkr_secrets_from_config, load_config
from src.connectivity.secrets import load_secrets


def _setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"collector_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IBKR snapshot collector (Step 3)")
    parser.add_argument(
        "--config",
        type=Path,
        default=BACKEND_ROOT / "configs" / "dev.yaml",
    )
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--session-date", type=str, default=None)
    parser.add_argument(
        "--max-duration",
        type=int,
        default=None,
        help="Stop after N seconds (useful for tests, e.g. 320 for one 5-min snapshot)",
    )
    args = parser.parse_args(argv)

    app_config = load_config(args.config, repo_root_path=REPO_ROOT)
    _setup_logging(app_config.paths.logs_dir)
    logger = logging.getLogger("run_collector")

    secrets = load_secrets(
        env_file=REPO_ROOT / ".env",
        defaults=ibkr_secrets_from_config(app_config),
    )
    secrets = type(secrets)(host=secrets.host, port=secrets.port, client_id=args.client_id)

    session_date = (
        dt.date.fromisoformat(args.session_date) if args.session_date else dt.date.today()
    )

    from dataclasses import replace

    from src.collectors.config import load_collector_config

    coll_cfg = load_collector_config(BACKEND_ROOT / "configs")
    if args.max_duration:
        coll_cfg = replace(
            coll_cfg,
            snapshot=replace(coll_cfg.snapshot, max_duration_seconds=args.max_duration),
        )

    adapter = IBKRAdapter(secrets, app_config)
    collector = RawCollector(adapter, coll_cfg, app_config.paths.artifacts_dir)

    try:
        adapter.connect()
        logger.info("Connected — building option-C universe for %s", session_date)
        collector.prepare_universe(session_date=session_date)
        summary = collector.run()
        print(json.dumps({
            "session_id": summary.session_id,
            "subscriptions": summary.subscription_count,
            "snapshots": summary.snapshot_count,
            "events": summary.event_count,
            "output_dir": str(summary.output_dir),
        }, indent=2))
        return 0
    except ConnectionRefusedError:
        logger.error("Connection refused — is IB Gateway running?")
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        logger.exception("Collector failed")
        return 1
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
