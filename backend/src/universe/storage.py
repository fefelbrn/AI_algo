"""Persistent storage for instrument master — SQLite + raw JSONL."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.universe.models import OptionInstrument, UnderlyingInstrument, UniverseSnapshot


class InstrumentMasterStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS instrument_master_underlyings (
                    instrument_key TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    sec_type TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    contract_id_broker INTEGER NOT NULL,
                    local_symbol TEXT,
                    listing_status TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    universe_version TEXT NOT NULL,
                    description TEXT,
                    PRIMARY KEY (as_of_date, instrument_key)
                );

                CREATE TABLE IF NOT EXISTS instrument_master_options (
                    instrument_key TEXT NOT NULL,
                    underlying_symbol TEXT NOT NULL,
                    sec_type TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    strike REAL NOT NULL,
                    right TEXT NOT NULL,
                    multiplier REAL NOT NULL,
                    trading_class TEXT NOT NULL,
                    contract_id_broker INTEGER,
                    local_symbol TEXT,
                    listing_status TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    universe_version TEXT NOT NULL,
                    maturity_years REAL,
                    PRIMARY KEY (as_of_date, instrument_key)
                );

                CREATE INDEX IF NOT EXISTS idx_options_underlying
                    ON instrument_master_options (as_of_date, underlying_symbol);
                CREATE INDEX IF NOT EXISTS idx_options_expiry
                    ON instrument_master_options (as_of_date, underlying_symbol, expiry);
                """
            )

    def save_snapshot(self, snapshot: UniverseSnapshot) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM instrument_master_underlyings WHERE as_of_date = ? AND universe_version = ?",
                (snapshot.as_of_date, snapshot.universe_version),
            )
            conn.execute(
                "DELETE FROM instrument_master_options WHERE as_of_date = ? AND universe_version = ?",
                (snapshot.as_of_date, snapshot.universe_version),
            )

            for u in snapshot.underlyings:
                conn.execute(
                    """
                    INSERT INTO instrument_master_underlyings (
                        instrument_key, symbol, sec_type, exchange, currency,
                        contract_id_broker, local_symbol, listing_status,
                        as_of_date, universe_version, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        u.instrument_key,
                        u.symbol,
                        u.sec_type,
                        u.exchange,
                        u.currency,
                        u.contract_id_broker,
                        u.local_symbol,
                        u.listing_status,
                        u.as_of_date,
                        u.universe_version,
                        u.description,
                    ),
                )

            for o in snapshot.options:
                conn.execute(
                    """
                    INSERT INTO instrument_master_options (
                        instrument_key, underlying_symbol, sec_type, exchange, currency,
                        expiry, expiry_date, strike, right, multiplier, trading_class,
                        contract_id_broker, local_symbol, listing_status,
                        as_of_date, universe_version, maturity_years
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        o.instrument_key,
                        o.underlying_symbol,
                        o.sec_type,
                        o.exchange,
                        o.currency,
                        o.expiry,
                        o.expiry_date.isoformat(),
                        o.strike,
                        o.right,
                        o.multiplier,
                        o.trading_class,
                        o.contract_id_broker,
                        o.local_symbol,
                        o.listing_status,
                        o.as_of_date,
                        o.universe_version,
                        o.maturity_years,
                    ),
                )
            conn.commit()

    def load_underlyings(
        self,
        as_of_date: str,
        *,
        universe_version: str | None = None,
    ) -> list[UnderlyingInstrument]:
        query = "SELECT * FROM instrument_master_underlyings WHERE as_of_date = ?"
        params: list[Any] = [as_of_date]
        if universe_version:
            query += " AND universe_version = ?"
            params.append(universe_version)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_underlying_from_row(r) for r in rows]

    def load_options(
        self,
        as_of_date: str,
        *,
        underlying_symbol: str | None = None,
        expiry: str | None = None,
        universe_version: str | None = None,
    ) -> list[OptionInstrument]:
        query = "SELECT * FROM instrument_master_options WHERE as_of_date = ?"
        params: list[Any] = [as_of_date]
        if universe_version:
            query += " AND universe_version = ?"
            params.append(universe_version)
        if underlying_symbol:
            query += " AND underlying_symbol = ?"
            params.append(underlying_symbol)
        if expiry:
            query += " AND expiry = ?"
            params.append(expiry)
        query += " ORDER BY underlying_symbol, expiry, strike, right"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_option_from_row(r) for r in rows]

    def latest_universe_version(self, as_of_date: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT universe_version FROM instrument_master_underlyings
                WHERE as_of_date = ?
                ORDER BY universe_version DESC
                LIMIT 1
                """,
                (as_of_date,),
            ).fetchone()
        return row["universe_version"] if row else None


def write_raw_payloads(
    artifacts_dir: Path,
    snapshot: UniverseSnapshot,
) -> Path:
    out_dir = artifacts_dir / "instrument_master" / f"dt={snapshot.as_of_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"raw_broker_{snapshot.universe_version}.jsonl"
    with raw_path.open("w", encoding="utf-8") as fh:
        for payload in snapshot.raw_broker_payloads:
            fh.write(json.dumps(payload, default=str) + "\n")
    return raw_path


def write_discovery_manifest(
    artifacts_dir: Path,
    snapshot: UniverseSnapshot,
) -> Path:
    out_dir = artifacts_dir / "instrument_master" / f"dt={snapshot.as_of_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"manifest_{snapshot.universe_version}.json"
    manifest = {
        "as_of_date": snapshot.as_of_date,
        "universe_version": snapshot.universe_version,
        "config_hash": snapshot.config_hash,
        "underlying_count": len(snapshot.underlyings),
        "option_count": len(snapshot.options),
        "qc_summary": snapshot.qc_summary,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _underlying_from_row(row: sqlite3.Row) -> UnderlyingInstrument:
    return UnderlyingInstrument(
        instrument_key=row["instrument_key"],
        symbol=row["symbol"],
        sec_type=row["sec_type"],
        exchange=row["exchange"],
        currency=row["currency"],
        contract_id_broker=row["contract_id_broker"],
        local_symbol=row["local_symbol"],
        listing_status=row["listing_status"],
        as_of_date=row["as_of_date"],
        universe_version=row["universe_version"],
        description=row["description"] or "",
    )


def _option_from_row(row: sqlite3.Row) -> OptionInstrument:
    import datetime as dt

    return OptionInstrument(
        instrument_key=row["instrument_key"],
        underlying_symbol=row["underlying_symbol"],
        sec_type=row["sec_type"],
        exchange=row["exchange"],
        currency=row["currency"],
        expiry=row["expiry"],
        expiry_date=dt.date.fromisoformat(row["expiry_date"]),
        strike=row["strike"],
        right=row["right"],
        multiplier=row["multiplier"],
        trading_class=row["trading_class"],
        contract_id_broker=row["contract_id_broker"],
        local_symbol=row["local_symbol"],
        listing_status=row["listing_status"],
        as_of_date=row["as_of_date"],
        universe_version=row["universe_version"],
        maturity_years=row["maturity_years"],
    )
