"""Thin IBKR adapter — isolates broker-specific behavior behind a stable interface."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ib_insync import IB, Stock

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
class QuoteSnapshot:
    symbol: str
    con_id: int
    bid: float | None
    ask: float | None
    last: float | None
    bid_size: float | None
    ask_size: float | None
    volume: float | None


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
    ) -> ResolvedContract:
        if sec_type != "STK":
            raise NotImplementedError(f"Step 1 supports STK only, got {sec_type}")
        contract = Stock(symbol, exchange, currency)
        qualified = self._ib.qualifyContracts(contract)
        if not qualified:
            raise ValueError(f"Could not resolve contract: {symbol} {exchange} {currency}")
        resolved = qualified[0]
        return ResolvedContract(
            symbol=resolved.symbol,
            sec_type=resolved.secType,
            exchange=resolved.exchange,
            currency=resolved.currency,
            con_id=resolved.conId,
            local_symbol=resolved.localSymbol or resolved.symbol,
        )

    def request_quote(
        self,
        contract: ResolvedContract,
        *,
        wait_seconds: float = 2.0,
    ) -> QuoteSnapshot:
        stock = Stock(contract.symbol, contract.exchange, contract.currency)
        stock.conId = contract.con_id
        ticker = self._ib.reqMktData(stock, "", False, False)
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
        self._ib.cancelMktData(stock)
        return snapshot


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
