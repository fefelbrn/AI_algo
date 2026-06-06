"""Thin IBKR adapter — isolates broker-specific behavior behind a stable interface."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import datetime as dt

from ib_insync import Contract, Future, IB, Index, Option, Stock

from src.connectivity.config import AppConfig
from src.connectivity.secrets import IBKRSecrets

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionState:
    connected: bool
    host: str
    port: int
    client_id: int
    accounts: tuple[str, ...]
    server_version: int | None


@dataclass(frozen=True)
class ResolvedContract:
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    con_id: int
    local_symbol: str


@dataclass(frozen=True)
class OptionChainParams:
    exchange: str
    underlying_con_id: int
    trading_class: str
    multiplier: float
    expirations: tuple[str, ...]
    strikes: tuple[float, ...]


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    con_id: int
    bid: float | None
    ask: float | None
    last: float | None
    bid_size: float | None
    ask_size: float | None
    volume: float | None

    @property
    def mid(self) -> float | None:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return None


@dataclass(frozen=True)
class FutureDetail:
    resolved: ResolvedContract
    expiry: str
    expiry_date: dt.date


class IBKRAdapter:
    """Minimal broker adapter for Step 1 smoke tests and health checks."""

    def __init__(self, secrets: IBKRSecrets, config: AppConfig) -> None:
        self._secrets = secrets
        self._config = config
        self._ib = IB()

    @property
    def ib(self) -> IB:
        return self._ib

    def connect(self) -> None:
        logger.info(
            "Connecting to IBKR at %s:%s (client_id=%s)",
            self._secrets.host,
            self._secrets.port,
            self._secrets.client_id,
        )
        self._ib.connect(
            self._secrets.host,
            self._secrets.port,
            clientId=self._secrets.client_id,
            timeout=self._config.ibkr.timeout_seconds,
            readonly=self._config.ibkr.readonly,
        )

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()
            logger.info("Disconnected from IBKR")

    def session_state(self) -> SessionState:
        accounts: tuple[str, ...] = ()
        server_version: int | None = None
        if self._ib.isConnected():
            accounts = tuple(self._ib.managedAccounts())
            server_version = self._ib.client.serverVersion()
        return SessionState(
            connected=self._ib.isConnected(),
            host=self._secrets.host,
            port=self._secrets.port,
            client_id=self._secrets.client_id,
            accounts=accounts,
            server_version=server_version,
        )

    def resolve_contract(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        sec_type: str = "STK",
        *,
        expiry: str | None = None,
        strike: float | None = None,
        right: str | None = None,
        trading_class: str | None = None,
        multiplier: float | None = None,
    ) -> ResolvedContract:
        return self.resolve_contract_generic(
            symbol,
            exchange,
            currency,
            sec_type,
            expiry=expiry,
            strike=strike,
            right=right,
            trading_class=trading_class,
            multiplier=multiplier,
        )

    def resolve_contract_generic(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        sec_type: str,
        *,
        expiry: str | None = None,
        strike: float | None = None,
        right: str | None = None,
        trading_class: str | None = None,
        multiplier: float | None = None,
    ) -> ResolvedContract:
        contract = self._build_contract(
            symbol,
            exchange,
            currency,
            sec_type,
            expiry=expiry,
            strike=strike,
            right=right,
            trading_class=trading_class,
            multiplier=multiplier,
        )
        qualified = self._ib.qualifyContracts(contract)
        if not qualified:
            raise ValueError(
                f"Could not resolve contract: {symbol} {sec_type} {exchange} "
                f"expiry={expiry} strike={strike} right={right}"
            )
        resolved = qualified[0]
        return ResolvedContract(
            symbol=resolved.symbol,
            sec_type=resolved.secType,
            exchange=resolved.exchange,
            currency=resolved.currency,
            con_id=resolved.conId,
            local_symbol=resolved.localSymbol or resolved.symbol,
        )

    def _build_contract(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        sec_type: str,
        *,
        expiry: str | None = None,
        strike: float | None = None,
        right: str | None = None,
        trading_class: str | None = None,
        multiplier: float | None = None,
    ) -> Contract:
        if sec_type in ("STK",):
            return Stock(symbol, exchange, currency)
        if sec_type in ("IND",):
            return Index(symbol, exchange, currency)
        if sec_type in ("FUT", "FOP"):
            return Future(symbol, exchange=exchange, currency=currency)
        if sec_type in ("OPT",):
            if not all([expiry, strike is not None, right]):
                raise ValueError("Option resolution requires expiry, strike, and right")
            contract = Option(
                symbol,
                expiry,
                float(strike),
                right,
                exchange,
                currency=currency,
                multiplier=multiplier or 100,
            )
            if trading_class:
                contract.tradingClass = trading_class
            return contract
        raise NotImplementedError(f"Unsupported sec_type: {sec_type}")

    def request_future_details(
        self,
        symbol: str,
        exchange: str,
        currency: str,
    ) -> list[FutureDetail]:
        template = Future(symbol, exchange=exchange, currency=currency)
        details = self._ib.reqContractDetails(template)
        results: list[FutureDetail] = []
        for detail in details:
            c = detail.contract
            if not c.lastTradeDateOrContractMonth:
                continue
            exp = c.lastTradeDateOrContractMonth
            if len(exp) == 8:
                exp_date = dt.datetime.strptime(exp, "%Y%m%d").date()
            else:
                exp_date = dt.datetime.strptime(exp + "01", "%Y%m%d").date()
            if exp_date < dt.date.today():
                continue
            resolved = ResolvedContract(
                symbol=c.symbol,
                sec_type=c.secType,
                exchange=c.exchange,
                currency=c.currency,
                con_id=c.conId,
                local_symbol=c.localSymbol or c.symbol,
            )
            results.append(FutureDetail(resolved=resolved, expiry=exp, expiry_date=exp_date))
        return results

    def request_option_chain_params(
        self,
        underlying: ResolvedContract,
    ) -> list[OptionChainParams]:
        chains = self._ib.reqSecDefOptParams(
            underlying.symbol,
            "",
            underlying.sec_type,
            underlying.con_id,
        )
        results: list[OptionChainParams] = []
        for chain in chains:
            multiplier = float(chain.multiplier) if chain.multiplier else 100.0
            results.append(
                OptionChainParams(
                    exchange=chain.exchange,
                    underlying_con_id=underlying.con_id,
                    trading_class=chain.tradingClass,
                    multiplier=multiplier,
                    expirations=tuple(sorted(chain.expirations)),
                    strikes=tuple(sorted(float(s) for s in chain.strikes)),
                )
            )
        return results

    def qualify_options_batch(
        self,
        contracts: list[Option],
    ) -> list[ResolvedContract | None]:
        if not contracts:
            return []
        self._ib.qualifyContracts(*contracts)
        results: list[ResolvedContract | None] = []
        for c in contracts:
            if c.conId:
                results.append(
                    ResolvedContract(
                        symbol=c.symbol,
                        sec_type=c.secType,
                        exchange=c.exchange,
                        currency=c.currency,
                        con_id=c.conId,
                        local_symbol=c.localSymbol or c.symbol,
                    )
                )
            else:
                results.append(None)
        return results

    def request_quote(
        self,
        contract: ResolvedContract,
        *,
        wait_seconds: float = 2.0,
    ) -> QuoteSnapshot:
        return self.request_quote_generic(contract, wait_seconds=wait_seconds)

    def request_quote_generic(
        self,
        contract: ResolvedContract,
        *,
        wait_seconds: float = 2.0,
    ) -> QuoteSnapshot:
        ib_contract = self._build_contract(
            contract.symbol,
            contract.exchange,
            contract.currency,
            contract.sec_type,
        )
        ib_contract.conId = contract.con_id
        ticker = self._ib.reqMktData(ib_contract, "", False, False)
        self._ib.sleep(wait_seconds)
        snapshot = QuoteSnapshot(
            symbol=contract.symbol,
            con_id=contract.con_id,
            bid=_safe_float(ticker.bid),
            ask=_safe_float(ticker.ask),
            last=_safe_float(ticker.last),
            bid_size=_safe_float(ticker.bidSize),
            ask_size=_safe_float(ticker.askSize),
            volume=_safe_float(ticker.volume),
        )
        self._ib.cancelMktData(ib_contract)
        return snapshot

    def snapshot_subscriptions(
        self,
        subscriptions: list[Any],
        *,
        wait_seconds: float = 2.0,
    ) -> list[tuple[Any, Any]]:
        """Request market data for all subscriptions, wait, return (sub, ticker) pairs."""
        pairs: list[tuple[Any, Any]] = []
        contracts: list[Contract] = []
        for sub in subscriptions:
            c = self._build_contract(
                sub.symbol,
                sub.exchange,
                sub.currency,
                sub.sec_type,
                expiry=sub.expiry,
                strike=sub.strike,
                right=sub.right,
            )
            c.conId = sub.con_id
            if sub.expiry and sub.sec_type == "OPT":
                c.lastTradeDateOrContractMonth = sub.expiry
            if sub.strike is not None and sub.sec_type == "OPT":
                c.strike = sub.strike
            if sub.right and sub.sec_type == "OPT":
                c.right = sub.right
            ticker = self._ib.reqMktData(c, "", False, False)
            pairs.append((sub, ticker))
            contracts.append(c)

        self._ib.sleep(wait_seconds)
        for c in contracts:
            self._ib.cancelMktData(c)
        return pairs


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:  # NaN
            return None
        if f <= 0:
            return None
        return f
    except (TypeError, ValueError):
        return None
