"""Unit tests for Step 4 storage platform."""

import datetime as dt
from pathlib import Path

import pyarrow.parquet as pq

from src.collectors.models import RawMarketEvent
from src.storage.config import load_storage_config
from src.storage.layers import DataLayer
from src.storage.parquet_writer import ParquetEventWriter
from src.storage.platform import StoragePlatform
from src.storage.schemas import PLATFORM_SCHEMA_VERSION, schema_for_layer
from src.storage.validation import ValidationError, validate_rows
from src.paths import backend_root


def test_load_storage_config():
    cfg = load_storage_config(backend_root() / "configs")
    assert cfg.version.startswith("storage_v")
    assert cfg.schema_version == "1.2.0"
    assert "raw_market_events" in cfg.retention


def test_all_layers_have_schemas():
    for layer in (
        DataLayer.RAW_MARKET_EVENTS,
        DataLayer.MARKET_STATE_SNAPSHOTS,
        DataLayer.FORWARD_CURVE,
        DataLayer.IV_POINTS,
        DataLayer.QC_RESULTS,
    ):
        schema = schema_for_layer(layer)
        assert "schema_version" in schema.names


def test_validate_rejects_missing_columns():
    cfg = load_storage_config(backend_root() / "configs")
    try:
        validate_rows(DataLayer.RAW_MARKET_EVENTS, [{"event_id": "x"}], cfg)
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


def test_platform_write_and_register(tmp_path):
    platform = StoragePlatform.open(tmp_path)
    rows = [
        {
            "event_id": "e1",
            "session_id": "sess",
            "snapshot_ts": "2026-06-09T14:00:00+00:00",
            "instrument_key": "k1",
            "product_name": "sp500",
            "role": "index",
            "symbol": "SPX",
            "sec_type": "IND",
            "field_name": "bid",
            "field_value": 100.0,
            "exchange_ts": None,
            "receipt_ts": "2026-06-09T14:00:01+00:00",
            "collector_ts": "2026-06-09T14:00:01+00:00",
            "con_id": 1,
            "tenor_label": None,
        }
    ]
    path, ref = platform.write_parquet_partition(
        DataLayer.RAW_MARKET_EVENTS,
        rows,
        trade_date="2026-06-09",
        filename="events_part_0000.parquet",
        run_id="run_test",
        session_id="sess",
    )
    table = pq.ParquetFile(path).read()
    assert table.num_rows == 1
    assert table.column("schema_version")[0].as_py() == PLATFORM_SCHEMA_VERSION

    parts = platform.metadata.list_partitions(DataLayer.RAW_MARKET_EVENTS.value, "2026-06-09")
    assert len(parts) == 1
    assert parts[0]["record_count"] == 1
    assert ref.partition_key.startswith("dt=2026-06-09")


def test_parquet_event_writer_via_platform(tmp_path):
    platform = StoragePlatform.open(tmp_path)
    writer = ParquetEventWriter(
        platform,
        session_id="test_session",
        trade_date="2026-06-09",
        run_id="run1",
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
    assert writer.total_events == 1
