"""Unit tests for Step 2 instrument master — no IBKR connection required."""

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from src.universe.config import load_universe_config
from src.universe.models import InstrumentKey, OptionInstrument, UnderlyingInstrument
from src.universe.qc import deduplicate_options, run_universe_qc
from src.universe.storage import InstrumentMasterStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sample_underlying() -> UnderlyingInstrument:
    key = InstrumentKey("SPY", "STK", "SMART", "USD", contract_id_broker=756733)
    return UnderlyingInstrument(
        instrument_key=key.to_string(),
        symbol="SPY",
        sec_type="STK",
        exchange="SMART",
        currency="USD",
        contract_id_broker=756733,
        local_symbol="SPY",
        listing_status="active",
        as_of_date="2026-06-06",
        universe_version="universe_v0.1.0_abc",
    )


def _sample_option(con_id: int = 100, strike: float = 500.0) -> OptionInstrument:
    key = InstrumentKey(
        "SPY", "OPT", "SMART", "USD",
        expiry="20260620", strike=strike, right="C",
        multiplier=100, contract_id_broker=con_id,
    )
    return OptionInstrument(
        instrument_key=key.to_string(),
        underlying_symbol="SPY",
        sec_type="OPT",
        exchange="SMART",
        currency="USD",
        expiry="20260620",
        expiry_date=dt.date(2026, 6, 20),
        strike=strike,
        right="C",
        multiplier=100,
        trading_class="SPY",
        contract_id_broker=con_id,
        local_symbol="SPY   250620C00500000",
        listing_status="active",
        as_of_date="2026-06-06",
        universe_version="universe_v0.1.0_abc",
        maturity_years=0.04,
    )


def test_instrument_key_roundtrip():
    key = InstrumentKey(
        "SPY", "OPT", "SMART", "USD",
        expiry="20260620", strike=500.0, right="C",
        multiplier=100, contract_id_broker=12345,
    )
    restored = InstrumentKey.from_string(key.to_string())
    assert restored.symbol == "SPY"
    assert restored.strike == 500.0
    assert restored.contract_id_broker == 12345


def test_deduplicate_options_keeps_lowest_con_id():
    opt_a = _sample_option(con_id=200)
    opt_b = _sample_option(con_id=100)
    deduped, removed = deduplicate_options([opt_a, opt_b])
    assert removed == 1
    assert len(deduped) == 1
    assert deduped[0].contract_id_broker == 100


def test_run_universe_qc_rejects_bad_multiplier():
    bad = replace(_sample_option(), multiplier=-1)
    _, options, report = run_universe_qc([_sample_underlying()], [bad])
    assert options == []
    assert report.summary()["rejected_option_count"] == 1


def test_storage_roundtrip(tmp_path):
    store = InstrumentMasterStore(tmp_path / "test.db")
    from src.universe.models import UniverseSnapshot

    version = "universe_v0.1.0_test"
    key = InstrumentKey("SPY", "STK", "SMART", "USD", contract_id_broker=756733)
    underlying = UnderlyingInstrument(
        instrument_key=key.to_string(),
        symbol="SPY",
        sec_type="STK",
        exchange="SMART",
        currency="USD",
        contract_id_broker=756733,
        local_symbol="SPY",
        listing_status="active",
        as_of_date="2026-06-06",
        universe_version=version,
    )
    snapshot = UniverseSnapshot(
        as_of_date="2026-06-06",
        universe_version=version,
        config_hash="abc123",
        underlyings=[underlying],
        options=[
            replace(_sample_option(), universe_version=version),
            replace(_sample_option(strike=510.0, con_id=101), universe_version=version),
        ],
    )
    store.save_snapshot(snapshot)

    loaded_u = store.load_underlyings("2026-06-06")
    loaded_o = store.load_options("2026-06-06", underlying_symbol="SPY")
    assert len(loaded_u) == 1
    assert len(loaded_o) == 2
    assert store.latest_universe_version("2026-06-06") == "universe_v0.1.0_test"


def test_load_universe_config():
    cfg = load_universe_config(PROJECT_ROOT / "configs")
    assert cfg.version.startswith("universe_v")
    assert len(cfg.underlyings) >= 1
    assert cfg.discovery.max_maturity_days == 90


def test_instrument_key_invalid_format():
    with pytest.raises(ValueError):
        InstrumentKey.from_string("invalid-key")
