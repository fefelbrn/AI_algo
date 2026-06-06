"""IBKR option-chain discovery — raw payloads and canonical normalization."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import asdict
from typing import Any

from ib_insync import Option

from src.connectivity.adapter import IBKRAdapter, OptionChainParams, ResolvedContract
from src.universe.config import UnderlyingSeed, UniverseConfig
from src.universe.models import InstrumentKey, OptionInstrument, UnderlyingInstrument, UniverseSnapshot
from src.universe.qc import run_universe_qc

logger = logging.getLogger(__name__)


def discover_universe(
    adapter: IBKRAdapter,
    universe_config: UniverseConfig,
    *,
    session_date: dt.date | None = None,
) -> UniverseSnapshot:
    session = session_date or dt.date.today()
    as_of = session.isoformat()
    universe_version = f"{universe_config.version}_{universe_config.config_hash}"

    underlyings: list[UnderlyingInstrument] = []
    options: list[OptionInstrument] = []
    raw_payloads: list[dict[str, Any]] = []

    for seed in universe_config.underlyings:
        if seed.sec_type not in universe_config.filters.sec_types:
            continue
        if universe_config.filters.exchanges and seed.exchange not in universe_config.filters.exchanges:
            continue

        logger.info("Discovering universe for %s", seed.symbol)
        resolved = adapter.resolve_contract(
            seed.symbol,
            seed.exchange,
            seed.currency,
            sec_type=seed.sec_type,
        )
        underlyings.append(_underlying_from_resolved(resolved, seed, as_of, universe_version))

        chains = adapter.request_option_chain_params(resolved)
        raw_payloads.append(
            {
                "underlying": seed.symbol,
                "underlying_con_id": resolved.con_id,
                "chains": [_chain_to_dict(c) for c in chains],
            }
        )

        selected_chains = _select_chains(chains, universe_config)
        candidates = _build_option_candidates(
            seed,
            resolved,
            selected_chains,
            session,
            universe_config,
        )
        logger.info(
            "%s: %d option candidates before qualification",
            seed.symbol,
            len(candidates),
        )

        qualified_map = _qualify_candidates(adapter, candidates, universe_config)
        for cand in candidates:
            q = qualified_map.get(cand["logical_key"])
            options.append(
                _option_from_candidate(
                    cand,
                    qualified=q,
                    as_of_date=as_of,
                    universe_version=universe_version,
                    session=session,
                )
            )

    clean_u, clean_o, qc_report = run_universe_qc(underlyings, options)
    return UniverseSnapshot(
        as_of_date=as_of,
        universe_version=universe_version,
        config_hash=universe_config.config_hash,
        underlyings=clean_u,
        options=clean_o,
        raw_broker_payloads=raw_payloads,
        qc_summary=qc_report.summary(),
    )


def _underlying_from_resolved(
    resolved: ResolvedContract,
    seed: UnderlyingSeed,
    as_of: str,
    universe_version: str,
) -> UnderlyingInstrument:
    key = InstrumentKey(
        symbol=resolved.symbol,
        sec_type=resolved.sec_type,
        exchange=resolved.exchange,
        currency=resolved.currency,
        contract_id_broker=resolved.con_id,
    )
    return UnderlyingInstrument(
        instrument_key=key.to_string(),
        symbol=resolved.symbol,
        sec_type=resolved.sec_type,
        exchange=resolved.exchange,
        currency=resolved.currency,
        contract_id_broker=resolved.con_id,
        local_symbol=resolved.local_symbol,
        listing_status="active",
        as_of_date=as_of,
        universe_version=universe_version,
        description=seed.description,
    )


def _chain_to_dict(chain: OptionChainParams) -> dict[str, Any]:
    return asdict(chain)


def _select_chains(
    chains: list[OptionChainParams],
    config: UniverseConfig,
) -> list[OptionChainParams]:
    if not chains:
        return []
    preferred = config.discovery.preferred_exchange
    if preferred:
        filtered = [c for c in chains if c.exchange == preferred]
        if filtered:
            return filtered
    # Prefer SMART-routed or the chain with the most expirations
    return sorted(chains, key=lambda c: (c.exchange != "SMART", -len(c.expirations)))


def _parse_expiry(expiry: str) -> dt.date:
    return dt.datetime.strptime(expiry, "%Y%m%d").date()


def _maturity_years(session: dt.date, expiry: dt.date) -> float:
    return max((expiry - session).days, 0) / 365.0


def _expiry_in_window(
    expiry: str,
    session: dt.date,
    config: UniverseConfig,
) -> bool:
    exp_date = _parse_expiry(expiry)
    dte = (exp_date - session).days
    return config.discovery.min_maturity_days <= dte <= config.discovery.max_maturity_days


def _build_option_candidates(
    seed: UnderlyingSeed,
    underlying: ResolvedContract,
    chains: list[OptionChainParams],
    session: dt.date,
    config: UniverseConfig,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    cap = config.discovery.max_contracts_per_underlying

    for chain in chains:
        expirations = [e for e in chain.expirations if _expiry_in_window(e, session, config)]
        for expiry in expirations:
            for strike in chain.strikes:
                for right in config.discovery.rights:
                    logical_key = "|".join(
                        [seed.symbol, chain.exchange, expiry, f"{strike:.6f}", right, chain.trading_class]
                    )
                    candidates.append(
                        {
                            "logical_key": logical_key,
                            "underlying_symbol": seed.symbol,
                            "exchange": chain.exchange,
                            "currency": seed.currency,
                            "expiry": expiry,
                            "strike": strike,
                            "right": right,
                            "multiplier": chain.multiplier,
                            "trading_class": chain.trading_class,
                            "underlying_con_id": underlying.con_id,
                        }
                    )
                    if cap and len(candidates) >= cap:
                        logger.warning(
                            "Hit max_contracts_per_underlying=%s for %s",
                            cap,
                            seed.symbol,
                        )
                        return candidates
    return candidates


def _qualify_candidates(
    adapter: IBKRAdapter,
    candidates: list[dict[str, Any]],
    config: UniverseConfig,
) -> dict[str, ResolvedContract]:
    batch_size = config.discovery.qualify_batch_size
    qualified_map: dict[str, ResolvedContract] = {}

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i : i + batch_size]
        contracts = [
            Option(
                c["underlying_symbol"],
                c["expiry"],
                c["strike"],
                c["right"],
                c["exchange"],
                currency=c["currency"],
                multiplier=c["multiplier"],
                tradingClass=c["trading_class"],
            )
            for c in batch
        ]
        try:
            resolved_batch = adapter.qualify_options_batch(contracts)
        except Exception:
            logger.exception("Batch qualification failed for batch starting at %d", i)
            continue

        for cand, resolved in zip(batch, resolved_batch, strict=True):
            if resolved is not None:
                qualified_map[cand["logical_key"]] = resolved

    return qualified_map


def _option_from_candidate(
    cand: dict[str, Any],
    *,
    qualified: ResolvedContract | None,
    as_of_date: str,
    universe_version: str,
    session: dt.date,
) -> OptionInstrument:
    expiry_date = _parse_expiry(cand["expiry"])
    con_id = qualified.con_id if qualified else None
    local_symbol = qualified.local_symbol if qualified else None
    exchange = qualified.exchange if qualified else cand["exchange"]

    key = InstrumentKey(
        symbol=cand["underlying_symbol"],
        sec_type="OPT",
        exchange=exchange,
        currency=cand["currency"],
        expiry=cand["expiry"],
        strike=cand["strike"],
        right=cand["right"],
        multiplier=cand["multiplier"],
        contract_id_broker=con_id,
    )
    return OptionInstrument(
        instrument_key=key.to_string(),
        underlying_symbol=cand["underlying_symbol"],
        sec_type="OPT",
        exchange=exchange,
        currency=cand["currency"],
        expiry=cand["expiry"],
        expiry_date=expiry_date,
        strike=cand["strike"],
        right=cand["right"],
        multiplier=cand["multiplier"],
        trading_class=cand["trading_class"],
        contract_id_broker=con_id,
        local_symbol=local_symbol,
        listing_status="active",
        as_of_date=as_of_date,
        universe_version=universe_version,
        maturity_years=_maturity_years(session, expiry_date),
    )
