"""Market-state snapshot models — typed outputs for Step 5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReferenceSpotResult:
    reference_price: float | None
    reference_type: str  # mid | last | carry_forward | missing
    bid: float | None
    ask: float | None
    last: float | None
    spread_pct: float | None
    flag_fallback: bool
    flag_stale: bool


@dataclass(frozen=True)
class MarketStateRow:
    snapshot_ts: str
    instrument_key: str
    product_name: str
    role: str
    symbol: str
    sec_type: str
    tenor_label: str | None
    reference_price: float | None
    reference_type: str
    bid: float | None
    ask: float | None
    last: float | None
    spread_pct: float | None
    quote_age_seconds: float | None
    flag_stale: bool
    flag_fallback: bool
    session_id: str
    source_event_partition: str

    def to_row(self) -> dict[str, Any]:
        return {
            "snapshot_ts": self.snapshot_ts,
            "instrument_key": self.instrument_key,
            "product_name": self.product_name,
            "role": self.role,
            "symbol": self.symbol,
            "sec_type": self.sec_type,
            "tenor_label": self.tenor_label or "",
            "reference_price": self.reference_price,
            "reference_type": self.reference_type,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "spread_pct": self.spread_pct,
            "quote_age_seconds": self.quote_age_seconds,
            "flag_stale": self.flag_stale,
            "flag_fallback": self.flag_fallback,
            "session_id": self.session_id,
            "source_event_partition": self.source_event_partition,
        }
