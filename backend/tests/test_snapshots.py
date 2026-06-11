"""Unit tests for Step 5 snapshot builder."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.snapshots.builder import build_snapshots_from_rows
from src.snapshots.config import load_snapshot_config
from src.snapshots.pipeline import run_snapshot_pipeline
from src.snapshots.spot import choose_reference_spot
from src.paths import backend_root
from src.storage.layers import DataLayer
from src.storage.schemas import RAW_MARKET_EVENTS_SCHEMA


def _raw_row(**kwargs):
    base = {
        "event_id": "e1",
        "session_id": "sess1",
        "snapshot_ts": "2026-06-09T14:00:00+00:00",
        "instrument_key": "SPX|IND|CBOE|USD|||||1",
        "product_name": "sp500",
        "role": "index",
        "symbol": "SPX",
        "sec_type": "IND",
        "field_name": "bid",
        "field_value": 5400.0,
        "exchange_ts": "2026-06-09T13:59:58+00:00",
        "receipt_ts": "2026-06-09T13:59:59+00:00",
        "collector_ts": "2026-06-09T14:00:00+00:00",
        "con_id": 1,
        "tenor_label": None,
        "schema_version": "1.0.0",
        "_source_partition": "/tmp/raw",
    }
    base.update(kwargs)
    return base


def test_choose_reference_mid():
    cfg = load_snapshot_config(backend_root() / "configs")
    ref = choose_reference_spot(bid=100.0, ask=100.2, last=100.1, role="index", config=cfg)
    assert ref.reference_type == "mid"
    assert ref.reference_price == 100.1
    assert not ref.flag_fallback


def test_choose_reference_fallback_last_on_wide_spread():
    cfg = load_snapshot_config(backend_root() / "configs")
    ref = choose_reference_spot(bid=100.0, ask=110.0, last=105.0, role="index", config=cfg)
    assert ref.reference_type == "last"
    assert ref.flag_fallback


def test_build_snapshots_deterministic():
    cfg = load_snapshot_config(backend_root() / "configs")
    rows = [
        _raw_row(field_name="bid", field_value=5400.0),
        _raw_row(event_id="e2", field_name="ask", field_value=5402.0),
        _raw_row(event_id="e3", field_name="last", field_value=5401.0),
    ]
    a = build_snapshots_from_rows(rows, cfg)
    b = build_snapshots_from_rows(rows, cfg)
    assert len(a) == 1
    assert a[0].reference_type == "mid"
    assert a[0].reference_price == 5401.0
    assert a == b


def test_pipeline_end_to_end(tmp_path):
    cfg = load_snapshot_config(backend_root() / "configs")
    session = "20260609T140000Z"
    raw_dir = (
        tmp_path / DataLayer.RAW_MARKET_EVENTS.value / "dt=2026-06-09" / f"session_id={session}"
    )
    raw_dir.mkdir(parents=True)
    rows = [
        _raw_row(field_name="bid", field_value=5400.0),
        _raw_row(event_id="e2", field_name="ask", field_value=5402.0),
    ]
    for i, r in enumerate(rows):
        r.pop("_source_partition", None)
        r["schema_version"] = "1.0.0"
    table = pa.Table.from_pylist(rows).cast(RAW_MARKET_EVENTS_SCHEMA)
    pq.write_table(table, raw_dir / "events_part_0000.parquet", use_dictionary=False)

    summary = run_snapshot_pipeline(tmp_path, "2026-06-09", session_id=session)
    assert summary.output_row_count == 1
    assert summary.output_path is not None
    assert summary.output_path.exists()
