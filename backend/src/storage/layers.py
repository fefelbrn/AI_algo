"""Canonical data layer identifiers."""

from __future__ import annotations

from enum import Enum


class DataLayer(str, Enum):
    RAW_MARKET_EVENTS = "raw_market_events"
    MARKET_STATE_SNAPSHOTS = "market_state_snapshots"
    FORWARD_CURVE = "forward_curve"
    FORWARD_DIAGNOSTICS = "forward_diagnostics"
    IV_POINTS = "iv_points"
    SURFACE_PARAMETERS = "surface_parameters"
    SURFACE_GRID = "surface_grid"
    PRICING_RESULTS = "pricing_results"
    POSITIONS = "positions"
    RISK_AGGREGATES = "risk_aggregates"
    SCENARIO_RESULTS = "scenario_results"
    QC_RESULTS = "qc_results"
    INSTRUMENT_MASTER = "instrument_master"

    @property
    def is_raw(self) -> bool:
        return self == DataLayer.RAW_MARKET_EVENTS

    @property
    def is_derived(self) -> bool:
        return not self.is_raw and self != DataLayer.INSTRUMENT_MASTER
