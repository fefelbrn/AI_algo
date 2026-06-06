"""Health checks for Step 1 — connectivity, session, clock, and market-data probe."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from ib_insync import IB

from src.connectivity.config import AppConfig


@dataclass
class HealthCheck:
    name: str
    status: str  # pass | warn | fail
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    checks: list[HealthCheck] = field(default_factory=list)
    overall_status: str = "fail"

    def add(self, check: HealthCheck) -> None:
        self.checks.append(check)

    def finalize(self) -> "HealthReport":
        statuses = {c.status for c in self.checks}
        if "fail" in statuses:
            self.overall_status = "fail"
        elif "warn" in statuses:
            self.overall_status = "warn"
        else:
            self.overall_status = "pass"
        return self


def _check_api_reachable(ib: IB) -> HealthCheck:
    if ib.isConnected():
        return HealthCheck(
            name="api_reachable",
            status="pass",
            message="IBKR API connection is active",
            details={"connected": True},
        )
    return HealthCheck(
        name="api_reachable",
        status="fail",
        message="IBKR API is not connected",
        details={"connected": False},
    )


def _check_login_valid(ib: IB) -> HealthCheck:
    try:
        accounts = ib.managedAccounts()
        if accounts:
            return HealthCheck(
                name="login_valid",
                status="pass",
                message="Session authenticated — managed accounts visible",
                details={"accounts": list(accounts)},
            )
        return HealthCheck(
            name="login_valid",
            status="warn",
            message="Connected but no managed accounts returned",
            details={"accounts": []},
        )
    except Exception as exc:
        return HealthCheck(
            name="login_valid",
            status="fail",
            message=f"Failed to verify session login: {exc}",
        )


def _check_clock_sync(ib: IB, config: AppConfig) -> HealthCheck:
    local_now = dt.datetime.now(dt.timezone.utc)
    try:
        server_time = ib.reqCurrentTime()
        if server_time.tzinfo is None:
            server_time = server_time.replace(tzinfo=dt.timezone.utc)
        skew = abs((server_time - local_now).total_seconds())
        status = "pass" if skew <= config.health.max_clock_skew_seconds else "warn"
        return HealthCheck(
            name="clock_sync",
            status=status,
            message=f"Clock skew {skew:.2f}s (limit {config.health.max_clock_skew_seconds}s)",
            details={
                "local_utc": local_now.isoformat(),
                "server_time": server_time.isoformat(),
                "skew_seconds": skew,
            },
        )
    except Exception as exc:
        return HealthCheck(
            name="clock_sync",
            status="fail",
            message=f"Could not request server time: {exc}",
        )


def _check_market_data_entitlement(
    ib: IB,
    *,
    symbol: str,
    exchange: str,
    currency: str,
) -> HealthCheck:
    from ib_insync import Stock

    contract = Stock(symbol, exchange, currency)
    try:
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            return HealthCheck(
                name="market_data_entitlement",
                status="fail",
                message=f"Contract resolution failed for {symbol}",
                details={"symbol": symbol, "exchange": exchange},
            )
        resolved = qualified[0]
        ticker = ib.reqMktData(resolved, "", False, False)
        ib.sleep(2)
        bid = ticker.bid
        ask = ticker.ask
        last = ticker.last
        ib.cancelMktData(resolved)

        has_quote = any(
            v is not None and v > 0 and v == v  # exclude NaN
            for v in (bid, ask, last)
        )
        if has_quote:
            return HealthCheck(
                name="market_data_entitlement",
                status="pass",
                message=f"Market data received for {symbol}",
                details={
                    "con_id": resolved.conId,
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                },
            )
        return HealthCheck(
            name="market_data_entitlement",
            status="warn",
            message=(
                f"Contract resolved but no live quote yet for {symbol} "
                "(market may be closed or delayed data only)"
            ),
            details={
                "con_id": resolved.conId,
                "bid": bid,
                "ask": ask,
                "last": last,
            },
        )
    except Exception as exc:
        return HealthCheck(
            name="market_data_entitlement",
            status="fail",
            message=f"Market data probe failed: {exc}",
            details={"symbol": symbol},
        )


def run_health_checks(
    ib: IB,
    config: AppConfig,
) -> HealthReport:
    report = HealthReport()
    report.add(_check_api_reachable(ib))
    if ib.isConnected():
        report.add(_check_login_valid(ib))
        report.add(_check_clock_sync(ib, config))
        report.add(
            _check_market_data_entitlement(
                ib,
                symbol=config.bootstrap.smoke_underlying,
                exchange=config.bootstrap.smoke_exchange,
                currency=config.bootstrap.smoke_currency,
            )
        )
    return report.finalize()
