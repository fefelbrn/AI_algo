"""Tenor bucket helpers — map calendar dates to canonical labels."""

from __future__ import annotations

import datetime as dt

from src.collectors.config import TenorBucket


def parse_yyyymmdd(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y%m%d").date()


def parse_yyyymm(value: str) -> dt.date:
    return dt.datetime.strptime(value + "01", "%Y%m%d").date()


def days_between(session: dt.date, expiry: dt.date) -> int:
    return max((expiry - session).days, 0)


def closest_tenor(
    session: dt.date,
    expiry: dt.date,
    tenors: tuple[TenorBucket, ...],
) -> tuple[TenorBucket, int]:
    """Return the closest tenor bucket and absolute day distance."""
    dte = days_between(session, expiry)
    best = min(tenors, key=lambda t: abs(t.days - dte))
    return best, abs(best.days - dte)


def pick_closest_expiry_to_tenor(
    expirations: list[str],
    session: dt.date,
    tenor: TenorBucket,
) -> str | None:
    if not expirations:
        return None
    target = session + dt.timedelta(days=tenor.days)

    def expiry_date(exp: str) -> dt.date:
        if len(exp) == 8:
            return parse_yyyymmdd(exp)
        if len(exp) == 6:
            return parse_yyyymm(exp)
        raise ValueError(f"Unsupported expiry format: {exp}")

    return min(expirations, key=lambda e: abs((expiry_date(e) - target).days))
