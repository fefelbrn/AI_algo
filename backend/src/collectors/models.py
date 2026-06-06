"""Collector data models."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class SubscriptionContract:
    """A contract selected for snapshot collection."""

    instrument_key: str
    product_name: str
    role: str  # index | future | option
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    con_id: int
    local_symbol: str
    tenor_label: str | None = None
    expiry: str | None = None
    strike: float | None = None
    right: str | None = None
    moneyness_band: str | None = None  # e.g. "0.90" for OTM put proxy


@dataclass(frozen=True)
class RawMarketEvent:
    event_id: str
    session_id: str
    snapshot_ts: str
    instrument_key: str
    product_name: str
    role: str
    symbol: str
    sec_type: str
    field_name: str
    field_value: float | None
    exchange_ts: str | None
    receipt_ts: str
    collector_ts: str
    con_id: int
    tenor_label: str | None = None
    metadata: dict[str, Any] | None = None

    @staticmethod
    def new_id() -> str:
        return str(uuid4())

    def to_row(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "snapshot_ts": self.snapshot_ts,
            "instrument_key": self.instrument_key,
            "product_name": self.product_name,
            "role": self.role,
            "symbol": self.symbol,
            "sec_type": self.sec_type,
            "field_name": self.field_name,
            "field_value": self.field_value,
            "exchange_ts": self.exchange_ts,
            "receipt_ts": self.receipt_ts,
            "collector_ts": self.collector_ts,
            "con_id": self.con_id,
            "tenor_label": self.tenor_label,
        }


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_ts(ts: dt.datetime | None = None) -> str:
    return (ts or utc_now()).isoformat()
