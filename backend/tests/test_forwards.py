"""Unit tests for Step 6 forward engine."""

import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.forwards.config import load_forward_config
from src.forwards.engine import build_forward_curve
from src.forwards.parity import implied_carry_rate, parity_forward
from src.forwards.pipeline import run_forward_pipeline
from src.paths import backend_root
from src.snapshots.builder import build_snapshots_from_rows
from src.snapshots.config import load_snapshot_config
from src.snapshots.models import MarketStateRow
from src.storage.layers import DataLayer
from src.storage.schemas import MARKET_STATE_SNAPSHOTS_SCHEMA


def _snap_row(**kwargs):
    base = {
        "snapshot_ts": "2026-06-09T14:00:00+00:00",
        "instrument_key": "SPX|IND|CBOE|USD|||||1",
        "product_name": "sp500",
        "role": "index",
        "symbol": "SPX",
        "sec_type": "IND",
        "tenor_label": "",
        "reference_price": 5400.0,
        "reference_type": "mid",
        "bid": 5399.0,
        "ask": 5401.0,
        "last": 5400.0,
        "spread_pct": 0.04,
        "quote_age_seconds": 1.0,
        "flag_stale": False,
        "flag_fallback": False,
        "session_id": "sess1",
        "source_event_partition": "/tmp",
    }
    base.update(kwargs)
    return base


def test_parity_forward_r_zero():
    # F = K + C - P when r=0
    f = parity_forward(100.0, 10.0, 8.0, risk_free_rate=0.0, maturity_years=0.25)
    assert abs(f - 102.0) < 1e-9


def test_implied_carry():
    q = implied_carry_rate(100.0, 102.0, risk_free_rate=0.0, maturity_years=1.0)
    assert q is not None
    assert abs(q - (-0.02)) < 0.001  # ln(1.02) ≈ 0.02


def test_build_forward_from_future_and_parity():
    cfg = load_forward_config(backend_root() / "configs")
    rows = [
        _snap_row(role="index", instrument_key="SPX|IND|CBOE|USD|||||1"),
        _snap_row(
            role="future",
            tenor_label="1m",
            instrument_key="ES|FUT|GLOBEX|USD|20260718||||2",
            reference_price=5410.0,
            symbol="ES",
            sec_type="FUT",
        ),
        _snap_row(
            role="option",
            tenor_label="1m",
            instrument_key="SPX|OPT|SMART|USD|20260718|5400.000000|C|100.0000|10",
            reference_price=50.0,
            symbol="SPX",
            sec_type="OPT",
        ),
        _snap_row(
            role="option",
            tenor_label="1m",
            instrument_key="SPX|OPT|SMART|USD|20260718|5400.000000|P|100.0000|11",
            reference_price=48.0,
            symbol="SPX",
            sec_type="OPT",
        ),
    ]
    curves, diags = build_forward_curve(rows, cfg)
    assert len(curves) >= 1
    one_m = [c for c in curves if c.tenor_label == "1m"]
    assert one_m
    assert one_m[0].forward_method == "future"
    assert one_m[0].spot_price == 5400.0
    assert len(diags) >= 1


def test_forward_pipeline_end_to_end(tmp_path):
    snap_cfg = load_snapshot_config(backend_root() / "configs")
    raw_events = []
    for field, val in [("bid", 5399.0), ("ask", 5401.0)]:
        raw_events.append({
            "event_id": f"e_{field}",
            "session_id": "sess1",
            "snapshot_ts": "2026-06-09T14:00:00+00:00",
            "instrument_key": "SPX|IND|CBOE|USD|||||1",
            "product_name": "sp500",
            "role": "index",
            "symbol": "SPX",
            "sec_type": "IND",
            "field_name": field,
            "field_value": val,
            "exchange_ts": None,
            "receipt_ts": "2026-06-09T14:00:00+00:00",
            "collector_ts": "2026-06-09T14:00:00+00:00",
            "con_id": 1,
            "tenor_label": None,
            "_source_partition": "/tmp",
        })
    snapshots = build_snapshots_from_rows(raw_events, snap_cfg)
    # add future row manually
    snapshots.append(
        MarketStateRow(
            snapshot_ts="2026-06-09T14:00:00+00:00",
            instrument_key="ES|FUT|GLOBEX|USD|20260718||||2",
            product_name="sp500",
            role="future",
            symbol="ES",
            sec_type="FUT",
            tenor_label="1m",
            reference_price=5410.0,
            reference_type="mid",
            bid=5409.0,
            ask=5411.0,
            last=5410.0,
            spread_pct=0.04,
            quote_age_seconds=1.0,
            flag_stale=False,
            flag_fallback=False,
            session_id="sess1",
            source_event_partition="/tmp",
        )
    )

    snap_dir = tmp_path / DataLayer.MARKET_STATE_SNAPSHOTS.value / "dt=2026-06-09" / "session_id=sess1"
    snap_dir.mkdir(parents=True)
    snap_rows = [s.to_row() for s in snapshots]
    for r in snap_rows:
        r["schema_version"] = "1.2.0"
    table = pa.Table.from_pylist(snap_rows).cast(MARKET_STATE_SNAPSHOTS_SCHEMA)
    pq.write_table(table, snap_dir / "snapshots.parquet", use_dictionary=False)

    summary = run_forward_pipeline(tmp_path, "2026-06-09", session_id="sess1")
    assert summary.forward_count >= 1
    assert summary.forward_path is not None
