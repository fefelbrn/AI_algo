"""Data-quality checks for instrument master records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.universe.models import OptionInstrument, UnderlyingInstrument


@dataclass
class QCResult:
    status: str  # pass | warn | fail
    reason_code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class UniverseQCReport:
    checks: list[QCResult] = field(default_factory=list)
    rejected_options: list[dict[str, Any]] = field(default_factory=list)
    duplicate_keys_removed: int = 0

    def add(self, result: QCResult) -> None:
        self.checks.append(result)

    def summary(self) -> dict[str, Any]:
        statuses = {c.status for c in self.checks}
        overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
        return {
            "overall_status": overall,
            "check_count": len(self.checks),
            "duplicate_keys_removed": self.duplicate_keys_removed,
            "rejected_option_count": len(self.rejected_options),
            "checks": [
                {
                    "status": c.status,
                    "reason_code": c.reason_code,
                    "message": c.message,
                    "context": c.context,
                }
                for c in self.checks
            ],
        }


def validate_underlying(record: UnderlyingInstrument) -> QCResult | None:
    if not record.currency:
        return QCResult("fail", "MISSING_CURRENCY", "Underlying missing currency")
    if record.contract_id_broker <= 0:
        return QCResult("fail", "INVALID_CON_ID", "Underlying has invalid broker contract id")
    return None


def validate_option(record: OptionInstrument) -> QCResult | None:
    if not record.currency:
        return QCResult("fail", "MISSING_CURRENCY", "Option missing currency", {"key": record.instrument_key})
    if record.multiplier <= 0:
        return QCResult("fail", "INVALID_MULTIPLIER", "Option has non-positive multiplier", {"key": record.instrument_key})
    if record.strike <= 0:
        return QCResult("fail", "INVALID_STRIKE", "Option has non-positive strike", {"key": record.instrument_key})
    if not record.expiry or len(record.expiry) != 8:
        return QCResult("fail", "INVALID_EXPIRY", "Option expiry must be YYYYMMDD", {"key": record.instrument_key})
    if record.right not in ("C", "P"):
        return QCResult("fail", "INVALID_RIGHT", "Option right must be C or P", {"key": record.instrument_key})
    return None


def deduplicate_options(options: list[OptionInstrument]) -> tuple[list[OptionInstrument], int]:
    """Remove duplicates deterministically — keep record with lowest con_id or first sorted key."""
    by_key: dict[str, OptionInstrument] = {}
    removed = 0
    for opt in sorted(options, key=lambda o: (o.instrument_key, o.contract_id_broker or 0)):
        logical_key = _logical_option_key(opt)
        existing = by_key.get(logical_key)
        if existing is None:
            by_key[logical_key] = opt
            continue
        removed += 1
        if _prefer(opt, existing):
            by_key[logical_key] = opt
    return list(by_key.values()), removed


def _logical_option_key(opt: OptionInstrument) -> str:
    return "|".join(
        [
            opt.underlying_symbol,
            opt.exchange,
            opt.expiry,
            f"{opt.strike:.6f}",
            opt.right,
            opt.trading_class,
        ]
    )


def _prefer(candidate: OptionInstrument, incumbent: OptionInstrument) -> bool:
    c_id = candidate.contract_id_broker or 0
    i_id = incumbent.contract_id_broker or 0
    if c_id and i_id:
        return c_id < i_id
    return bool(c_id) and not i_id


def run_universe_qc(
    underlyings: list[UnderlyingInstrument],
    options: list[OptionInstrument],
) -> tuple[list[UnderlyingInstrument], list[OptionInstrument], UniverseQCReport]:
    report = UniverseQCReport()
    clean_underlyings: list[UnderlyingInstrument] = []
    clean_options: list[OptionInstrument] = []

    for u in underlyings:
        issue = validate_underlying(u)
        if issue:
            report.add(issue)
        else:
            clean_underlyings.append(u)

    for opt in options:
        issue = validate_option(opt)
        if issue:
            report.add(issue)
            report.rejected_options.append({"instrument_key": opt.instrument_key, "reason": issue.reason_code})
        else:
            clean_options.append(opt)

    deduped, removed = deduplicate_options(clean_options)
    report.duplicate_keys_removed = removed
    if removed:
        report.add(
            QCResult(
                "warn",
                "DUPLICATES_REMOVED",
                f"Removed {removed} duplicate option records deterministically",
                {"count": removed},
            )
        )

    if not clean_underlyings:
        report.add(QCResult("fail", "NO_UNDERLYINGS", "No valid underlyings in universe"))

    report.add(
        QCResult(
            "pass",
            "UNIVERSE_COUNTS",
            f"Universe contains {len(clean_underlyings)} underlyings and {len(deduped)} options",
            {"underlyings": len(clean_underlyings), "options": len(deduped)},
        )
    )
    return clean_underlyings, deduped, report
