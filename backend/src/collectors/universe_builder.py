"""Build option-C subscription universe: index + futures + ATM option subset."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from ib_insync import Contract, Future, Index, Option, Stock

from src.collectors.config import CollectorConfig, ContractSpec, ProductConfig
from src.collectors.models import SubscriptionContract
from src.collectors.tenors import pick_closest_expiry_to_tenor
from src.connectivity.adapter import IBKRAdapter, ResolvedContract

logger = logging.getLogger(__name__)


@dataclass
class BuiltUniverse:
    subscriptions: list[SubscriptionContract]
    reference_spots: dict[str, float]
    diagnostics: list[dict]


def build_subscription_universe(
    adapter: IBKRAdapter,
    config: CollectorConfig,
    *,
    session_date: dt.date | None = None,
) -> BuiltUniverse:
    session = session_date or dt.date.today()
    subs: list[SubscriptionContract] = []
    spots: dict[str, float] = {}
    diagnostics: list[dict] = []

    for product in config.products:
        logger.info("Building universe for product %s", product.name)
        index_resolved, index_spot = _resolve_index_with_spot(adapter, product)
        spots[product.name] = index_spot
        subs.append(_to_subscription(index_resolved, product.name, "index", tenor_label=None))

        future_subs, fut_diag = _select_futures(adapter, product, config, session)
        subs.extend(future_subs)
        diagnostics.extend(fut_diag)

        option_subs, opt_diag = _select_options(
            adapter, product, config, session, index_spot, index_resolved
        )
        subs.extend(option_subs)
        diagnostics.extend(opt_diag)

    return BuiltUniverse(subscriptions=subs, reference_spots=spots, diagnostics=diagnostics)


def _make_instrument_key(resolved: ResolvedContract, **extra: str | float | None) -> str:
    parts = [
        resolved.symbol,
        resolved.sec_type,
        resolved.exchange,
        resolved.currency,
        str(extra.get("expiry") or ""),
        f"{extra['strike']:.6f}" if extra.get("strike") is not None else "",
        str(extra.get("right") or ""),
        "",
        str(resolved.con_id),
    ]
    return "|".join(parts)


def _to_subscription(
    resolved: ResolvedContract,
    product_name: str,
    role: str,
    *,
    tenor_label: str | None,
    expiry: str | None = None,
    strike: float | None = None,
    right: str | None = None,
    moneyness_band: str | None = None,
) -> SubscriptionContract:
    return SubscriptionContract(
        instrument_key=_make_instrument_key(
            resolved, expiry=expiry, strike=strike, right=right
        ),
        product_name=product_name,
        role=role,
        symbol=resolved.symbol,
        sec_type=resolved.sec_type,
        exchange=resolved.exchange,
        currency=resolved.currency,
        con_id=resolved.con_id,
        local_symbol=resolved.local_symbol,
        tenor_label=tenor_label,
        expiry=expiry,
        strike=strike,
        right=right,
        moneyness_band=moneyness_band,
    )


def _contract_from_spec(spec: ContractSpec) -> Contract:
    if spec.sec_type == "IND":
        return Index(spec.symbol, spec.exchange, spec.currency)
    if spec.sec_type == "STK":
        return Stock(spec.symbol, spec.exchange, spec.currency)
    if spec.sec_type == "FUT":
        return Future(spec.symbol, exchange=spec.exchange, currency=spec.currency)
    if spec.sec_type == "OPT":
        raise ValueError("Use Option() with expiry/strike/right")
    raise ValueError(f"Unsupported sec_type: {spec.sec_type}")


def _resolve_with_fallback(
    adapter: IBKRAdapter,
    spec: ContractSpec,
) -> ResolvedContract:
    try:
        return adapter.resolve_contract_generic(spec.symbol, spec.exchange, spec.currency, spec.sec_type)
    except Exception as exc:
        if spec.fallback is None:
            raise
        logger.warning(
            "Failed to resolve %s %s, trying fallback %s: %s",
            spec.symbol,
            spec.sec_type,
            spec.fallback.symbol,
            exc,
        )
        fb = spec.fallback
        return adapter.resolve_contract_generic(fb.symbol, fb.exchange, fb.currency, fb.sec_type)


def _resolve_index_with_spot(
    adapter: IBKRAdapter,
    product: ProductConfig,
) -> tuple[ResolvedContract, float]:
    resolved = _resolve_with_fallback(adapter, product.index)
    quote = adapter.request_quote_generic(resolved)
    spot = quote.mid or quote.last
    if spot is None:
        raise ValueError(f"No reference spot for {product.name} ({resolved.symbol})")
    return resolved, spot


def _select_futures(
    adapter: IBKRAdapter,
    product: ProductConfig,
    config: CollectorConfig,
    session: dt.date,
) -> tuple[list[SubscriptionContract], list[dict]]:
    subs: list[SubscriptionContract] = []
    diagnostics: list[dict] = []
    spec = product.futures

    try:
        details = adapter.request_future_details(spec.symbol, spec.exchange, spec.currency)
    except Exception as exc:
        logger.warning("Future discovery failed for %s: %s", product.name, exc)
        diagnostics.append({"product": product.name, "role": "future", "error": str(exc)})
        return subs, diagnostics

    if not details:
        diagnostics.append({"product": product.name, "role": "future", "error": "no_listed_futures"})
        return subs, diagnostics

    for tenor in config.tenors:
        target = session + dt.timedelta(days=tenor.days)
        best = min(details, key=lambda d: abs((d.expiry_date - target).days))
        distance = abs((best.expiry_date - target).days)
        sub = _to_subscription(
            best.resolved,
            product.name,
            "future",
            tenor_label=tenor.label,
            expiry=best.expiry,
        )
        subs.append(sub)
        diagnostics.append(
            {
                "product": product.name,
                "role": "future",
                "tenor_label": tenor.label,
                "expiry": best.expiry,
                "distance_days": distance,
                "con_id": best.resolved.con_id,
            }
        )
    return subs, diagnostics


def _select_options(
    adapter: IBKRAdapter,
    product: ProductConfig,
    config: CollectorConfig,
    session: dt.date,
    spot: float,
    index_resolved: ResolvedContract,
) -> tuple[list[SubscriptionContract], list[dict]]:
    subs: list[SubscriptionContract] = []
    diagnostics: list[dict] = []
    opt_spec = product.options

    try:
        opt_underlying = _resolve_with_fallback(adapter, opt_spec)
        chains = adapter.request_option_chain_params(opt_underlying)
    except Exception as exc:
        logger.warning("Option chain failed for %s: %s", product.name, exc)
        diagnostics.append({"product": product.name, "role": "option", "error": str(exc)})
        return subs, diagnostics

    if not chains:
        return subs, diagnostics

    chain = max(chains, key=lambda c: len(c.expirations))
    expirations = list(chain.expirations)
    strikes = sorted(chain.strikes)

    if not strikes:
        return subs, diagnostics

    atm_strike = min(strikes, key=lambda s: abs(s - spot))

    for tenor in config.tenors:
        expiry = pick_closest_expiry_to_tenor(expirations, session, tenor)
        if expiry is None:
            continue

        target_strikes: list[tuple[float, str]] = []
        for band in config.options_subset.moneyness_bands:
            target = spot * band
            strike = min(strikes, key=lambda s: abs(s - target))
            target_strikes.append((strike, f"{band:.2f}"))

        seen_strikes: set[float] = set()
        for strike, band_label in target_strikes:
            if strike in seen_strikes:
                continue
            seen_strikes.add(strike)

            rights: list[str] = []
            if config.options_subset.include_calls:
                rights.append("C")
            if config.options_subset.include_puts:
                rights.append("P")

            for right in rights:
                try:
                    resolved = adapter.resolve_contract_generic(
                        opt_underlying.symbol,
                        chain.exchange,
                        opt_underlying.currency,
                        "OPT",
                        expiry=expiry,
                        strike=strike,
                        right=right,
                        trading_class=chain.trading_class,
                        multiplier=chain.multiplier,
                    )
                except Exception:
                    continue

                subs.append(
                    _to_subscription(
                        resolved,
                        product.name,
                        "option",
                        tenor_label=tenor.label,
                        expiry=expiry,
                        strike=strike,
                        right=right,
                        moneyness_band=band_label,
                    )
                )
                diagnostics.append(
                    {
                        "product": product.name,
                        "role": "option",
                        "tenor_label": tenor.label,
                        "expiry": expiry,
                        "strike": strike,
                        "right": right,
                        "moneyness_band": band_label,
                        "atm_strike": atm_strike,
                        "spot": spot,
                    }
                )

    return subs, diagnostics
