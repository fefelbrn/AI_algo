"""Forward curve engine — futures + parity, MAD QC, tenor tagging."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

from src.collectors.tenors import days_between, parse_yyyymmdd
from src.forwards.config import ForwardEngineConfig
from src.forwards.models import ForwardCurveResult, ForwardDiagnostic
from src.forwards.parity import implied_carry_rate, option_mid, parity_forward
from src.forwards.robust import filter_by_mad, weighted_mean
from src.universe.models import InstrumentKey


def _parse_snapshot_date(snapshot_ts: str) -> dt.date:
    return dt.datetime.fromisoformat(snapshot_ts.replace("Z", "+00:00")).date()


def _maturity_years(session: dt.date, expiry: str) -> float:
    exp = parse_yyyymmdd(expiry) if len(expiry) == 8 else dt.datetime.strptime(expiry + "01", "%Y%m%d").date()
    return max(days_between(session, exp), 1) / 365.0


def _liquidity_weight(spread_pct: float | None, config: ForwardEngineConfig) -> float:
    if not config.use_inverse_spread:
        return 1.0
    if spread_pct is None or spread_pct <= 0:
        return 1.0
    return 1.0 / spread_pct


def _confidence(
    *,
    n_candidates: int,
    n_accepted: int,
    residual_pct: float,
    has_future: bool,
) -> float:
    count_score = min(n_accepted / max(n_candidates, 1), 1.0)
    residual_score = max(0.0, 1.0 - residual_pct / 10.0)
    future_bonus = 0.1 if has_future else 0.0
    return min(1.0, 0.5 * count_score + 0.4 * residual_score + future_bonus)


def build_forward_curve(
    snapshot_rows: list[dict[str, Any]],
    config: ForwardEngineConfig,
) -> tuple[list[ForwardCurveResult], list[ForwardDiagnostic]]:
    """Pure engine: market-state rows in, forward curve + diagnostics out."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in snapshot_rows:
        key = (row["snapshot_ts"], row["product_name"])
        groups[key].append(row)

    curves: list[ForwardCurveResult] = []
    diagnostics: list[ForwardDiagnostic] = []

    for (snapshot_ts, product_name), rows in sorted(groups.items()):
        session_date = _parse_snapshot_date(snapshot_ts)
        index_rows = [r for r in rows if r["role"] == "index" and r.get("reference_price")]
        if not index_rows:
            continue
        spot = float(index_rows[0]["reference_price"])
        underlying_symbol = index_rows[0]["symbol"]

        futures_by_tenor = {
            r["tenor_label"]: r
            for r in rows
            if r["role"] == "future" and r.get("tenor_label") and r.get("reference_price")
        }

        options_by_tenor: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if r["role"] == "option" and r.get("tenor_label"):
                options_by_tenor[r["tenor_label"]].append(r)

        tenors_seen = set(futures_by_tenor) | set(options_by_tenor)
        for tenor_label in sorted(tenors_seen):
            result, diags = _estimate_tenor_forward(
                snapshot_ts=snapshot_ts,
                product_name=product_name,
                underlying_symbol=underlying_symbol,
                tenor_label=tenor_label,
                spot=spot,
                session_date=session_date,
                future_row=futures_by_tenor.get(tenor_label),
                option_rows=options_by_tenor.get(tenor_label, []),
                config=config,
            )
            diagnostics.extend(diags)
            if result is not None:
                curves.append(result)

    return curves, diagnostics


def _estimate_tenor_forward(
    *,
    snapshot_ts: str,
    product_name: str,
    underlying_symbol: str,
    tenor_label: str,
    spot: float,
    session_date: dt.date,
    future_row: dict | None,
    option_rows: list[dict],
    config: ForwardEngineConfig,
) -> tuple[ForwardCurveResult | None, list[ForwardDiagnostic]]:
    diags: list[ForwardDiagnostic] = []
    tenor_bucket = next((t for t in config.tenors if t.label == tenor_label), None)
    if tenor_bucket is None:
        return None, diags

    expiry = _resolve_expiry(future_row, option_rows)
    if not expiry:
        return None, diags

    maturity = _maturity_years(session_date, expiry)
    tenor_dist = abs(days_between(session_date, parse_yyyymmdd(expiry)) - tenor_bucket.days)

    parity_candidates = _parity_candidates(option_rows, maturity, config, snapshot_ts, product_name, tenor_label, expiry)
    diags.extend(parity_candidates[1])

    future_price: float | None = None
    if future_row and future_row.get("reference_price"):
        future_price = float(future_row["reference_price"])
        diags.append(
            ForwardDiagnostic(
                snapshot_ts=snapshot_ts,
                product_name=product_name,
                tenor_label=tenor_label,
                expiry=expiry,
                strike=0.0,
                call_mid=None,
                put_mid=None,
                forward_estimate=future_price,
                weight=1.0,
                parity_residual=0.0,
                method="future",
                quality_flag="accepted",
                source_snapshot_ts=snapshot_ts,
            )
        )

    accepted = parity_candidates[0]
    parity_forward_price: float | None = None
    if accepted:
        pairs = [(c.forward_estimate, c.weight) for c in accepted]
        parity_forward_price = weighted_mean(pairs)

    forward_price, method, quality = _choose_forward(
        future_price, parity_forward_price, len(accepted), config
    )
    if forward_price is None:
        return None, diags

    residual_pct = 0.0
    if accepted and parity_forward_price:
        residuals = [abs(c.forward_estimate - parity_forward_price) / parity_forward_price * 100 for c in accepted]
        residual_pct = sum(residuals) / len(residuals)

    carry = implied_carry_rate(spot, forward_price, risk_free_rate=config.risk_free_rate, maturity_years=maturity)
    confidence = _confidence(
        n_candidates=len(parity_candidates[0]) + (1 if future_price else 0),
        n_accepted=len(accepted) + (1 if future_price else 0),
        residual_pct=residual_pct,
        has_future=future_price is not None,
    )

    if confidence >= 0.7:
        quality_label = "high"
    elif confidence >= 0.4:
        quality_label = "medium"
    else:
        quality_label = "low"

    return (
        ForwardCurveResult(
            snapshot_ts=snapshot_ts,
            product_name=product_name,
            underlying_symbol=underlying_symbol,
            maturity_years=maturity,
            expiry=expiry,
            forward_price=forward_price,
            forward_confidence=confidence,
            tenor_label=tenor_label,
            tenor_distance_days=tenor_dist,
            spot_price=spot,
            implied_carry_rate=carry,
            forward_method=method,
            quality_label=quality_label,
            source_snapshot_ts=snapshot_ts,
        ),
        diags,
    )


def _expiry_from_key(instrument_key: str) -> str | None:
    parts = instrument_key.split("|")
    if len(parts) == 9 and parts[4] and len(parts[4]) == 8:
        return parts[4]
    try:
        return InstrumentKey.from_string(instrument_key).expiry
    except ValueError:
        return None


def _resolve_expiry(future_row: dict | None, option_rows: list[dict]) -> str | None:
    if future_row:
        exp = _expiry_from_key(future_row["instrument_key"])
        if exp:
            return exp
    for row in option_rows:
        exp = _expiry_from_key(row["instrument_key"])
        if exp:
            return exp
    return None


def _parity_candidates(
    option_rows: list[dict],
    maturity_years: float,
    config: ForwardEngineConfig,
    snapshot_ts: str,
    product_name: str,
    tenor_label: str,
    expiry: str,
) -> tuple[list, list[ForwardDiagnostic]]:
    from src.forwards.models import ForwardCandidate

    calls: dict[float, dict] = {}
    puts: dict[float, dict] = {}
    for row in option_rows:
        try:
            key = InstrumentKey.from_string(row["instrument_key"])
        except ValueError:
            continue
        if key.strike is None or key.right not in ("C", "P"):
            continue
        mid = option_mid(row.get("bid"), row.get("ask"), row.get("reference_price"))
        if mid is None or mid < config.min_option_mid:
            continue
        if key.right == "C":
            calls[key.strike] = row
            calls[key.strike]["_mid"] = mid
        else:
            puts[key.strike] = row
            puts[key.strike]["_mid"] = mid

    candidates: list[ForwardCandidate] = []
    all_diags: list[ForwardDiagnostic] = []

    for strike in sorted(set(calls) & set(puts)):
        c_mid = calls[strike]["_mid"]
        p_mid = puts[strike]["_mid"]
        f_est = parity_forward(
            strike, c_mid, p_mid,
            risk_free_rate=config.risk_free_rate,
            maturity_years=maturity_years,
        )
        spread = calls[strike].get("spread_pct") or puts[strike].get("spread_pct")
        weight = _liquidity_weight(spread, config)
        candidates.append(
            ForwardCandidate(
                strike=strike,
                call_mid=c_mid,
                put_mid=p_mid,
                forward_estimate=f_est,
                weight=weight,
                parity_residual=0.0,
                method="parity",
            )
        )

    if not candidates:
        return [], all_diags

    med = sorted(c.forward_estimate for c in candidates)[len(candidates) // 2]
    candidates = [
        ForwardCandidate(
            strike=c.strike,
            call_mid=c.call_mid,
            put_mid=c.put_mid,
            forward_estimate=c.forward_estimate,
            weight=c.weight,
            parity_residual=abs(c.forward_estimate - med),
            method=c.method,
        )
        for c in candidates
    ]

    values = [c.forward_estimate for c in candidates]
    kept, rejected = filter_by_mad(candidates, values, threshold=config.mad_z_threshold)

    final_kept = []
    for c in kept:
        residual_pct = abs(c.forward_estimate - med) / med * 100 if med else 0
        flag = "accepted" if residual_pct <= config.max_parity_residual_pct else "rejected_wide_residual"
        all_diags.append(
            ForwardDiagnostic(
                snapshot_ts=snapshot_ts,
                product_name=product_name,
                tenor_label=tenor_label,
                expiry=expiry,
                strike=c.strike,
                call_mid=c.call_mid,
                put_mid=c.put_mid,
                forward_estimate=c.forward_estimate,
                weight=c.weight,
                parity_residual=c.parity_residual,
                method="parity",
                quality_flag=flag,
                source_snapshot_ts=snapshot_ts,
            )
        )
        if flag == "accepted":
            final_kept.append(c)

    for c in rejected:
        all_diags.append(
            ForwardDiagnostic(
                snapshot_ts=snapshot_ts,
                product_name=product_name,
                tenor_label=tenor_label,
                expiry=expiry,
                strike=c.strike,
                call_mid=c.call_mid,
                put_mid=c.put_mid,
                forward_estimate=c.forward_estimate,
                weight=c.weight,
                parity_residual=c.parity_residual,
                method="parity",
                quality_flag="rejected_outlier",
                source_snapshot_ts=snapshot_ts,
            )
        )

    return final_kept, all_diags


def _choose_forward(
    future_price: float | None,
    parity_price: float | None,
    n_parity: int,
    config: ForwardEngineConfig,
) -> tuple[float | None, str, str]:
    if config.prefer_future_when_available and future_price is not None:
        if config.blend_future_parity and parity_price is not None:
            return (future_price + parity_price) / 2.0, "blended", "ok"
        return future_price, "future", "ok"
    if parity_price is not None and n_parity >= config.min_candidates_after_qc:
        return parity_price, "parity", "ok"
    if future_price is not None:
        return future_price, "future", "ok"
    return None, "missing", "rejected"
