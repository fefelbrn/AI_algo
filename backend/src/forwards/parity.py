"""Put-call parity forward estimation."""

from __future__ import annotations

import math


def parity_forward(
    strike: float,
    call_mid: float,
    put_mid: float,
    *,
    risk_free_rate: float,
    maturity_years: float,
) -> float:
    """F = K + exp(rT) * (C - P)  — Black-76 / equity parity form."""
    return strike + math.exp(risk_free_rate * maturity_years) * (call_mid - put_mid)


def implied_carry_rate(
    spot: float,
    forward: float,
    *,
    risk_free_rate: float,
    maturity_years: float,
) -> float | None:
    """From F = S * exp((r - q) * T)  =>  q = r - ln(F/S) / T."""
    if spot <= 0 or forward <= 0 or maturity_years <= 0:
        return None
    return risk_free_rate - math.log(forward / spot) / maturity_years


def option_mid(bid: float | None, ask: float | None, reference: float | None) -> float | None:
    if reference is not None and reference > 0:
        return reference
    if bid is not None and ask is not None and bid > 0 and ask >= bid:
        return (bid + ask) / 2.0
    return None
