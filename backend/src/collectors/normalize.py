"""Normalize IBKR tickers into raw market events — one event per field."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ib_insync import Ticker

from src.collectors.models import RawMarketEvent, SubscriptionContract, iso_ts, utc_now


FIELD_MAP = ("bid", "ask", "last", "bidSize", "askSize", "volume", "open", "high", "low", "close")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        if f != f or f <= 0:
            return None
        return f
    except (TypeError, ValueError):
        return None


def ticker_to_events(
    sub: SubscriptionContract,
    ticker: Ticker,
    *,
    session_id: str,
    snapshot_ts: dt.datetime,
    receipt_ts: dt.datetime | None = None,
) -> list[RawMarketEvent]:
    receipt = receipt_ts or utc_now()
    collector_ts = utc_now()
    snap_iso = iso_ts(snapshot_ts)
    events: list[RawMarketEvent] = []

    exchange_ts: str | None = None
    if ticker.time is not None:
        t = ticker.time
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        exchange_ts = t.isoformat()

    for field in FIELD_MAP:
        value = _safe_float(getattr(ticker, field, None))
        if value is None:
            continue
        events.append(
            RawMarketEvent(
                event_id=RawMarketEvent.new_id(),
                session_id=session_id,
                snapshot_ts=snap_iso,
                instrument_key=sub.instrument_key,
                product_name=sub.product_name,
                role=sub.role,
                symbol=sub.symbol,
                sec_type=sub.sec_type,
                field_name=field,
                field_value=value,
                exchange_ts=exchange_ts,
                receipt_ts=iso_ts(receipt),
                collector_ts=iso_ts(collector_ts),
                con_id=sub.con_id,
                tenor_label=sub.tenor_label,
                metadata={
                    "moneyness_band": sub.moneyness_band,
                    "expiry": sub.expiry,
                    "strike": sub.strike,
                    "right": sub.right,
                },
            )
        )
    return events
