#!/usr/bin/env python3
"""Step 5 — build market-state snapshots from raw Parquet events."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from _paths import BACKEND_ROOT, REPO_ROOT, setup_import_path

setup_import_path()

from src.connectivity.config import load_config
from src.snapshots.pipeline import run_snapshot_pipeline


def _setup_logging(logs_dir: Path) -> None:
    import datetime as dt

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"snapshots_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build market-state snapshots (Step 5)")
    parser.add_argument("--config", type=Path, default=BACKEND_ROOT / "configs" / "dev.yaml")
    parser.add_argument("--trade-date", type=str, required=True, help="YYYY-MM-DD")
    parser.add_argument("--session-id", type=str, default=None, help="Optional session filter")
    args = parser.parse_args(argv)

    app_config = load_config(args.config, repo_root_path=REPO_ROOT)
    _setup_logging(app_config.paths.logs_dir)

    summary = run_snapshot_pipeline(
        app_config.paths.artifacts_dir,
        args.trade_date,
        session_id=args.session_id,
        config_dir=BACKEND_ROOT / "configs",
    )

    print(json.dumps({
        "trade_date": summary.trade_date,
        "session_id": summary.session_id,
        "input_events": summary.input_event_count,
        "output_rows": summary.output_row_count,
        "output_path": str(summary.output_path) if summary.output_path else None,
        "completeness": summary.completeness,
    }, indent=2))

    if summary.output_row_count == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
