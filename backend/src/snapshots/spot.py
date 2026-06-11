"""Reference spot selection — mid, last, carry-forward with explicit labels."""

from __future__ import annotations

from src.snapshots.config import RoleThresholds, SnapshotBuilderConfig
from src.snapshots.models import ReferenceSpotResult


def spread_pct(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return 100.0 * (ask - bid) / mid


def choose_reference_spot(
    *,
    bid: float | None,
    ask: float | None,
    last: float | None,
    role: str,
    config: SnapshotBuilderConfig,
    carry_forward_price: float | None = None,
    is_stale: bool = False,
) -> ReferenceSpotResult:
    """Deterministic reference selection per roadmap Step 5."""
    thresholds: RoleThresholds = config.thresholds.get(
        role, config.thresholds.get("index", RoleThresholds(300, 0.5))
    )
    sp = spread_pct(bid, ask)
    mid_usable = (
        bid is not None
        and ask is not None
        and bid > 0
        and ask >= bid
        and (sp is None or sp <= thresholds.max_spread_pct)
    )

    ref_price: float | None = None
    ref_type = "missing"
    flag_fallback = False

    for choice in config.reference_priority:
        if choice == "mid" and mid_usable:
            ref_price = (bid + ask) / 2.0  # type: ignore[operator]
            ref_type = "mid"
            break
        if choice == "last" and last is not None and last > 0:
            ref_price = last
            ref_type = "last"
            flag_fallback = not mid_usable
            break
        if (
            choice == "carry_forward"
            and config.allow_carry_forward
            and carry_forward_price is not None
            and carry_forward_price > 0
        ):
            ref_price = carry_forward_price
            ref_type = "carry_forward"
            flag_fallback = True
            break

    if ref_type == "missing" and last is not None and last > 0:
        ref_price = last
        ref_type = "last"
        flag_fallback = True

    return ReferenceSpotResult(
        reference_price=ref_price,
        reference_type=ref_type,
        bid=bid,
        ask=ask,
        last=last,
        spread_pct=sp,
        flag_fallback=flag_fallback,
        flag_stale=is_stale,
    )
