"""Unit tests for Step 3 collector — no IBKR required."""

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pyarrow.parquet as pq

from src.collectors.config import TenorBucket, load_collector_config
from src.collectors.models import RawMarketEvent, SubscriptionContract
from src.collectors.normalize import ticker_to_events
from src.collectors.tenors import pick_closest_expiry_to_tenor
from src.paths import backend_root
from src.storage.parquet_writer import ParquetEventWriter
from src.storage.platform import StoragePlatform


def _sub() -> SubscriptionContract:
    return SubscriptionContract(
        instrument_key="SPX|IND|CBOE|USD|||||123",
        product_name="sp500",
        role="index",
        symbol="SPX",
        sec_type="IND",
        exchange="CBOE",
        currency="USD",
        con_id=123,
        local_symbol="SPX",
    )


def test_load_collector_config():
    cfg = load_collector_config(backend_root() / "configs")
    assert cfg.version.startswith("collector_v")
    assert len(cfg.products) == 2
    assert cfg.snapshot.interval_seconds == 300
    assert len(cfg.tenors) == 9


def test_pick_closest_expiry_to_tenor():
    session = dt.date(2026, 6, 9)
    tenor = TenorBucket("1m", 30)
    expiries = ["20260620", "20260718", "20260815"]
    picked = pick_closest_expiry_to_tenor(expiries, session, tenor)
    assert picked == "20260718"


def test_ticker_to_events_field_granularity():
    ticker = MagicMock()
    ticker.bid = 540.0
    ticker.ask = 541.0
    ticker.last = 540.5
    ticker.bidSize = 100
    ticker.askSize = 200
    ticker.volume = 1_000_000
    ticker.open = None
    ticker.high = None
    ticker.low = None
    ticker.close = None
    ticker.time = None

    events = ticker_to_events(
        _sub(),
        ticker,
        session_id="sess1",
        snapshot_ts=dt.datetime(2026, 6, 9, 14, 0, tzinfo=dt.timezone.utc),
    )
    field_names = {e.field_name for e in events}
    assert "bid" in field_names
    assert "ask" in field_names
    assert all(e.session_id == "sess1" for e in events)
    assert all(e.product_name == "sp500" for e in events)


def test_parquet_writer_roundtrip(tmp_path):
    platform = StoragePlatform.open(tmp_path)
    writer = ParquetEventWriter(
        platform,
        session_id="test_session",
        trade_date="2026-06-09",
        run_id="run_test",
    )
    event = RawMarketEvent(
        event_id="e1",
        session_id="test_session",
        snapshot_ts="2026-06-09T14:00:00+00:00",
        instrument_key="k1",
        product_name="sp500",
        role="index",
        symbol="SPX",
        sec_type="IND",
        field_name="bid",
        field_value=100.0,
        exchange_ts=None,
        receipt_ts="2026-06-09T14:00:01+00:00",
        collector_ts="2026-06-09T14:00:01+00:00",
        con_id=1,
        tenor_label=None,
    )
    path = writer.write_events([event])
    assert path is not None
    table = pq.ParquetFile(path).read()
    assert table.num_rows == 1
    assert table.column("field_name")[0].as_py() == "bid"
