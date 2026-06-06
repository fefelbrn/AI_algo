"""Canonical instrument models — stable keys and typed records."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal

OptionRight = Literal["C", "P"]
ListingStatus = Literal["active", "inactive", "unknown"]


@dataclass(frozen=True)
class InstrumentKey:
    """Stable composite key used across all tables."""

    symbol: str
    sec_type: str
    exchange: str
    currency: str
    expiry: str | None = None  # YYYYMMDD for options, None for underlyings
    strike: float | None = None
    right: OptionRight | None = None
    multiplier: float | None = None
    contract_id_broker: int | None = None

    def to_string(self) -> str:
        parts = [
            self.symbol,
            self.sec_type,
            self.exchange,
            self.currency,
            self.expiry or "",
            f"{self.strike:.6f}" if self.strike is not None else "",
            self.right or "",
            f"{self.multiplier:.4f}" if self.multiplier is not None else "",
            str(self.contract_id_broker or ""),
        ]
        return "|".join(parts)

    @classmethod
    def from_string(cls, key: str) -> "InstrumentKey":
        parts = key.split("|")
        if len(parts) != 9:
            raise ValueError(f"Invalid instrument key format: {key}")
        expiry = parts[4] or None
        strike = float(parts[5]) if parts[5] else None
        right = parts[6] or None
        multiplier = float(parts[7]) if parts[7] else None
        con_id = int(parts[8]) if parts[8] else None
        if right and right not in ("C", "P"):
            raise ValueError(f"Invalid option right: {right}")
        return cls(
            symbol=parts[0],
            sec_type=parts[1],
            exchange=parts[2],
            currency=parts[3],
            expiry=expiry,
            strike=strike,
            right=right,  # type: ignore[arg-type]
            multiplier=multiplier,
            contract_id_broker=con_id,
        )


@dataclass(frozen=True)
class UnderlyingInstrument:
    instrument_key: str
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    contract_id_broker: int
    local_symbol: str
    listing_status: ListingStatus
    as_of_date: str
    universe_version: str
    description: str = ""


@dataclass(frozen=True)
class OptionInstrument:
    instrument_key: str
    underlying_symbol: str
    sec_type: str
    exchange: str
    currency: str
    expiry: str  # YYYYMMDD
    expiry_date: dt.date
    strike: float
    right: OptionRight
    multiplier: float
    trading_class: str
    contract_id_broker: int | None
    local_symbol: str | None
    listing_status: ListingStatus
    as_of_date: str
    universe_version: str
    maturity_years: float | None = None


@dataclass
class UniverseSnapshot:
    as_of_date: str
    universe_version: str
    config_hash: str
    underlyings: list[UnderlyingInstrument] = field(default_factory=list)
    options: list[OptionInstrument] = field(default_factory=list)
    raw_broker_payloads: list[dict[str, Any]] = field(default_factory=list)
    qc_summary: dict[str, Any] = field(default_factory=dict)
