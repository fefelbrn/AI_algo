"""Pure snapshot builder — raw events in, market state rows out."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from src.snapshots.config import SnapshotBuilderConfig
from src.snapshots.models import MarketStateRow
from src.snapshots.spot import choose_reference_spot


def _parse_ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except ValueError:
        return None


def _quote_age_seconds(snapshot_ts: str, receipt_ts: str | None, exchange_ts: str | None) -> float | None:
    snap = _parse_ts(snapshot_ts)
    if snap is None:
        return None
    ref = _parse_ts(exchange_ts) or _parse_ts(receipt_ts)
    if ref is None:
        return None
    return max((snap - ref).total_seconds(), 0.0)


def _pivot_events(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Group by (snapshot_ts, instrument_key, session_id) and pivot fields."""
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["snapshot_ts"], row["instrument_key"], row["session_id"])
        if key not in groups:
            groups[key] = {
                "snapshot_ts": row["snapshot_ts"],
                "instrument_key": row["instrument_key"],
                "session_id": row["session_id"],
                "product_name": row["product_name"],
                "role": row["role"],
                "symbol": row["symbol"],
                "sec_type": row["sec_type"],
                "tenor_label": row.get("tenor_label"),
                "source_event_partition": row.get("_source_partition", ""),
                "fields": {},
                "receipt_ts": row.get("receipt_ts"),
                "exchange_ts": row.get("exchange_ts"),
            }
        fname = row["field_name"]
        fval = row.get("field_value")
        if fval is not None:
            groups[key]["fields"][fname] = float(fval)
        if row.get("receipt_ts"):
            groups[key]["receipt_ts"] = row["receipt_ts"]
        if row.get("exchange_ts"):
            groups[key]["exchange_ts"] = row["exchange_ts"]
    return groups


def build_snapshots_from_rows(
    rows: list[dict[str, Any]],
    config: SnapshotBuilderConfig,
) -> list[MarketStateRow]:
    """Build market-state snapshots deterministically from raw event rows."""
    pivoted = _pivot_events(rows)
    sorted_keys = sorted(pivoted.keys())

    last_trusted_ref: dict[str, float] = {}
    results: list[MarketStateRow] = []

    for key in sorted_keys:
        g = pivoted[key]
        fields = g["fields"]
        bid = fields.get("bid")
        ask = fields.get("ask")
        last = fields.get("last")
        role = g["role"]
        instrument_key = g["instrument_key"]

        age = _quote_age_seconds(g["snapshot_ts"], g.get("receipt_ts"), g.get("exchange_ts"))
        thresholds = config.thresholds.get(role, config.thresholds["index"])
        is_stale = age is not None and age > thresholds.max_quote_age_seconds

        carry = last_trusted_ref.get(instrument_key) if config.allow_carry_forward else None
        ref = choose_reference_spot(
            bid=bid,
            ask=ask,
            last=last,
            role=role,
            config=config,
            carry_forward_price=carry,
            is_stale=is_stale,
        )

        if ref.reference_price is not None and ref.reference_type in ("mid", "last"):
            last_trusted_ref[instrument_key] = ref.reference_price

        results.append(
            MarketStateRow(
                snapshot_ts=g["snapshot_ts"],
                instrument_key=instrument_key,
                product_name=g["product_name"],
                role=role,
                symbol=g["symbol"],
                sec_type=g["sec_type"],
                tenor_label=g.get("tenor_label") or None,
                reference_price=ref.reference_price,
                reference_type=ref.reference_type,
                bid=ref.bid,
                ask=ref.ask,
                last=ref.last,
                spread_pct=ref.spread_pct,
                quote_age_seconds=age,
                flag_stale=is_stale,
                flag_fallback=ref.flag_fallback,
                session_id=g["session_id"],
                source_event_partition=g.get("source_event_partition", ""),
            )
        )

    return results


def build_snapshots_from_events(
    events: list[Any],
    config: SnapshotBuilderConfig,
) -> list[MarketStateRow]:
    rows = [e.to_row() if hasattr(e, "to_row") else dict(e) for e in events]
    for row in rows:
        row.setdefault("schema_version", "1.0.0")
    return build_snapshots_from_rows(rows, config)
