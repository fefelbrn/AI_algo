"""Forward curve models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ForwardCandidate:
    strike: float
    call_mid: float | None
    put_mid: float | None
    forward_estimate: float
    weight: float
    parity_residual: float
    method: str  # parity | future


@dataclass(frozen=True)
class ForwardDiagnostic:
    snapshot_ts: str
    product_name: str
    tenor_label: str
    expiry: str
    strike: float
    call_mid: float | None
    put_mid: float | None
    forward_estimate: float
    weight: float
    parity_residual: float
    method: str
    quality_flag: str
    source_snapshot_ts: str

    def to_row(self) -> dict[str, Any]:
        return {
            "snapshot_ts": self.snapshot_ts,
            "product_name": self.product_name,
            "tenor_label": self.tenor_label,
            "expiry": self.expiry,
            "strike": self.strike,
            "call_mid": self.call_mid,
            "put_mid": self.put_mid,
            "forward_estimate": self.forward_estimate,
            "weight": self.weight,
            "parity_residual": self.parity_residual,
            "method": self.method,
            "quality_flag": self.quality_flag,
            "source_snapshot_ts": self.source_snapshot_ts,
        }


@dataclass(frozen=True)
class ForwardCurveResult:
    snapshot_ts: str
    product_name: str
    underlying_symbol: str
    maturity_years: float
    expiry: str
    forward_price: float
    forward_confidence: float
    tenor_label: str
    tenor_distance_days: int
    spot_price: float
    implied_carry_rate: float | None
    forward_method: str
    quality_label: str
    source_snapshot_ts: str

    def to_row(self) -> dict[str, Any]:
        return {
            "snapshot_ts": self.snapshot_ts,
            "product_name": self.product_name,
            "underlying_symbol": self.underlying_symbol,
            "maturity_years": self.maturity_years,
            "expiry": self.expiry,
            "forward_price": self.forward_price,
            "forward_confidence": self.forward_confidence,
            "tenor_label": self.tenor_label,
            "tenor_distance_days": self.tenor_distance_days,
            "spot_price": self.spot_price,
            "implied_carry_rate": self.implied_carry_rate,
            "forward_method": self.forward_method,
            "quality_label": self.quality_label,
            "source_snapshot_ts": self.source_snapshot_ts,
        }
