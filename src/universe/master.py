"""Instrument master service — public API for universe access."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

from src.connectivity.adapter import IBKRAdapter
from src.universe.config import UniverseConfig, load_universe_config
from src.universe.discovery import discover_universe
from src.universe.models import InstrumentKey, OptionInstrument, UnderlyingInstrument, UniverseSnapshot
from src.universe.storage import (
    InstrumentMasterStore,
    write_discovery_manifest,
    write_raw_payloads,
)

logger = logging.getLogger(__name__)


class UnresolvedContractError(Exception):
    def __init__(self, key: InstrumentKey | str, diagnostics: dict | None = None) -> None:
        self.key = key
        self.diagnostics = diagnostics or {}
        super().__init__(f"Unresolved contract: {key}")


@dataclass
class InstrumentMaster:
    store: InstrumentMasterStore
    universe_config: UniverseConfig
    artifacts_dir: Path
    adapter: IBKRAdapter | None = None

    @classmethod
    def from_config(
        cls,
        config_dir: Path,
        artifacts_dir: Path,
        *,
        adapter: IBKRAdapter | None = None,
    ) -> "InstrumentMaster":
        universe_config = load_universe_config(config_dir)
        db_path = artifacts_dir / universe_config.storage.subdir / "master.db"
        return cls(
            store=InstrumentMasterStore(db_path),
            universe_config=universe_config,
            artifacts_dir=artifacts_dir,
            adapter=adapter,
        )

    def discover_and_persist(
        self,
        *,
        session_date: dt.date | None = None,
        adapter: IBKRAdapter | None = None,
    ) -> UniverseSnapshot:
        broker = adapter or self.adapter
        if broker is None:
            raise ValueError("An IBKRAdapter is required for discovery")

        snapshot = discover_universe(broker, self.universe_config, session_date=session_date)
        self.store.save_snapshot(snapshot)
        write_raw_payloads(self.artifacts_dir, snapshot)
        write_discovery_manifest(self.artifacts_dir, snapshot)
        logger.info(
            "Persisted universe %s — %d underlyings, %d options",
            snapshot.universe_version,
            len(snapshot.underlyings),
            len(snapshot.options),
        )
        return snapshot

    def load_active_universe(
        self,
        session_date: str | dt.date,
        *,
        universe_version: str | None = None,
    ) -> UniverseSnapshot:
        as_of = session_date.isoformat() if isinstance(session_date, dt.date) else session_date
        version = universe_version or self.store.latest_universe_version(as_of)
        if not version:
            raise FileNotFoundError(f"No universe stored for session date {as_of}")

        underlyings = self.store.load_underlyings(as_of, universe_version=version)
        options = self.store.load_options(as_of, universe_version=version)
        return UniverseSnapshot(
            as_of_date=as_of,
            universe_version=version,
            config_hash=self.universe_config.config_hash,
            underlyings=underlyings,
            options=options,
        )

    def get_underlying(
        self,
        symbol: str,
        session_date: str | dt.date,
        *,
        universe_version: str | None = None,
    ) -> UnderlyingInstrument:
        as_of = session_date.isoformat() if isinstance(session_date, dt.date) else session_date
        version = universe_version or self.store.latest_universe_version(as_of)
        underlyings = self.store.load_underlyings(as_of, universe_version=version)
        matches = [u for u in underlyings if u.symbol == symbol]
        if not matches:
            raise UnresolvedContractError(
                symbol,
                {"session_date": as_of, "reason": "underlying_not_in_universe"},
            )
        return matches[0]

    def get_option_chain(
        self,
        symbol: str,
        expiry: str,
        session_date: str | dt.date,
        *,
        universe_version: str | None = None,
    ) -> list[OptionInstrument]:
        as_of = session_date.isoformat() if isinstance(session_date, dt.date) else session_date
        version = universe_version or self.store.latest_universe_version(as_of)
        return self.store.load_options(
            as_of,
            underlying_symbol=symbol,
            expiry=expiry,
            universe_version=version,
        )

    def resolve_contract(
        self,
        key: InstrumentKey | str,
        session_date: str | dt.date,
        *,
        universe_version: str | None = None,
        adapter: IBKRAdapter | None = None,
    ) -> UnderlyingInstrument | OptionInstrument:
        instrument_key = key if isinstance(key, InstrumentKey) else InstrumentKey.from_string(key)
        as_of = session_date.isoformat() if isinstance(session_date, dt.date) else session_date
        version = universe_version or self.store.latest_universe_version(as_of)

        if instrument_key.sec_type == "STK":
            return self.get_underlying(instrument_key.symbol, as_of, universe_version=version)

        options = self.store.load_options(
            as_of,
            underlying_symbol=instrument_key.symbol,
            expiry=instrument_key.expiry,
            universe_version=version,
        )
        for opt in options:
            if (
                opt.strike == instrument_key.strike
                and opt.right == instrument_key.right
                and opt.multiplier == instrument_key.multiplier
            ):
                if opt.contract_id_broker:
                    return opt
                broker = adapter or self.adapter
                if broker is None:
                    raise UnresolvedContractError(
                        instrument_key.to_string(),
                        {"reason": "missing_con_id_and_no_adapter"},
                    )
                resolved = broker.resolve_contract(
                    opt.underlying_symbol,
                    opt.exchange,
                    opt.currency,
                    sec_type="OPT",
                    expiry=opt.expiry,
                    strike=opt.strike,
                    right=opt.right,
                    trading_class=opt.trading_class,
                    multiplier=opt.multiplier,
                )
                return OptionInstrument(
                    instrument_key=instrument_key.to_string(),
                    underlying_symbol=opt.underlying_symbol,
                    sec_type=opt.sec_type,
                    exchange=resolved.exchange,
                    currency=resolved.currency,
                    expiry=opt.expiry,
                    expiry_date=opt.expiry_date,
                    strike=opt.strike,
                    right=opt.right,
                    multiplier=opt.multiplier,
                    trading_class=opt.trading_class,
                    contract_id_broker=resolved.con_id,
                    local_symbol=resolved.local_symbol,
                    listing_status=opt.listing_status,
                    as_of_date=opt.as_of_date,
                    universe_version=opt.universe_version,
                    maturity_years=opt.maturity_years,
                )

        raise UnresolvedContractError(
            instrument_key.to_string(),
            {
                "session_date": as_of,
                "reason": "option_not_in_universe",
                "symbol": instrument_key.symbol,
                "expiry": instrument_key.expiry,
                "strike": instrument_key.strike,
                "right": instrument_key.right,
            },
        )
