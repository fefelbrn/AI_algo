"""Versioned PyArrow schemas for all platform data layers."""

from __future__ import annotations

import pyarrow as pa

from src.storage.layers import DataLayer

PLATFORM_SCHEMA_VERSION = "1.2.0"

# ── Step 3 — raw (live + replay identical) ─────────────────────────────
RAW_MARKET_EVENTS_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("session_id", pa.string()),
        ("snapshot_ts", pa.string()),
        ("instrument_key", pa.string()),
        ("product_name", pa.string()),
        ("role", pa.string()),
        ("symbol", pa.string()),
        ("sec_type", pa.string()),
        ("field_name", pa.string()),
        ("field_value", pa.float64()),
        ("exchange_ts", pa.string()),
        ("receipt_ts", pa.string()),
        ("collector_ts", pa.string()),
        ("con_id", pa.int64()),
        ("tenor_label", pa.string()),
        ("schema_version", pa.string()),
    ]
)

# ── Step 5 — normalized market state ───────────────────────────────────
MARKET_STATE_SNAPSHOTS_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("instrument_key", pa.string()),
        ("product_name", pa.string()),
        ("role", pa.string()),
        ("symbol", pa.string()),
        ("sec_type", pa.string()),
        ("tenor_label", pa.string()),
        ("reference_price", pa.float64()),
        ("reference_type", pa.string()),
        ("bid", pa.float64()),
        ("ask", pa.float64()),
        ("last", pa.float64()),
        ("spread_pct", pa.float64()),
        ("quote_age_seconds", pa.float64()),
        ("flag_stale", pa.bool_()),
        ("flag_fallback", pa.bool_()),
        ("session_id", pa.string()),
        ("source_event_partition", pa.string()),
        ("schema_version", pa.string()),
    ]
)

# ── Step 6 — forwards ──────────────────────────────────────────────────
FORWARD_CURVE_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("product_name", pa.string()),
        ("underlying_symbol", pa.string()),
        ("maturity_years", pa.float64()),
        ("expiry", pa.string()),
        ("forward_price", pa.float64()),
        ("forward_confidence", pa.float64()),
        ("tenor_label", pa.string()),
        ("tenor_distance_days", pa.int64()),
        ("spot_price", pa.float64()),
        ("implied_carry_rate", pa.float64()),
        ("forward_method", pa.string()),
        ("quality_label", pa.string()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

FORWARD_DIAGNOSTICS_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("product_name", pa.string()),
        ("tenor_label", pa.string()),
        ("expiry", pa.string()),
        ("strike", pa.float64()),
        ("call_mid", pa.float64()),
        ("put_mid", pa.float64()),
        ("forward_estimate", pa.float64()),
        ("weight", pa.float64()),
        ("parity_residual", pa.float64()),
        ("method", pa.string()),
        ("quality_flag", pa.string()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

IV_POINTS_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("contract_key", pa.string()),
        ("underlying_symbol", pa.string()),
        ("expiry", pa.string()),
        ("strike", pa.float64()),
        ("right", pa.string()),
        ("implied_vol", pa.float64()),
        ("solver_converged", pa.bool_()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

SURFACE_PARAMETERS_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("product_name", pa.string()),
        ("maturity_years", pa.float64()),
        ("surface_model", pa.string()),
        ("fit_params_json", pa.string()),
        ("fit_rmse", pa.float64()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

SURFACE_GRID_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("product_name", pa.string()),
        ("maturity_years", pa.float64()),
        ("moneyness", pa.float64()),
        ("total_variance", pa.float64()),
        ("implied_vol", pa.float64()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

PRICING_RESULTS_SCHEMA = pa.schema(
    [
        ("snapshot_ts", pa.string()),
        ("contract_key", pa.string()),
        ("model_price", pa.float64()),
        ("greek_delta", pa.float64()),
        ("greek_gamma", pa.float64()),
        ("greek_vega", pa.float64()),
        ("greek_theta", pa.float64()),
        ("pricer_version", pa.string()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

POSITIONS_SCHEMA = pa.schema(
    [
        ("valuation_ts", pa.string()),
        ("portfolio_id", pa.string()),
        ("contract_key", pa.string()),
        ("quantity", pa.float64()),
        ("schema_version", pa.string()),
    ]
)

RISK_AGGREGATES_SCHEMA = pa.schema(
    [
        ("valuation_ts", pa.string()),
        ("portfolio_id", pa.string()),
        ("group_key", pa.string()),
        ("greek_delta", pa.float64()),
        ("greek_gamma", pa.float64()),
        ("greek_vega", pa.float64()),
        ("dollar_gamma", pa.float64()),
        ("dollar_vega", pa.float64()),
        ("source_snapshot_ts", pa.string()),
        ("schema_version", pa.string()),
    ]
)

SCENARIO_RESULTS_SCHEMA = pa.schema(
    [
        ("valuation_ts", pa.string()),
        ("portfolio_id", pa.string()),
        ("scenario_id", pa.string()),
        ("contract_key", pa.string()),
        ("scenario_pnl", pa.float64()),
        ("schema_version", pa.string()),
    ]
)

QC_RESULTS_SCHEMA = pa.schema(
    [
        ("run_id", pa.string()),
        ("check_name", pa.string()),
        ("target_key", pa.string()),
        ("qc_status", pa.string()),
        ("reason_code", pa.string()),
        ("measured_value", pa.float64()),
        ("threshold_version", pa.string()),
        ("schema_version", pa.string()),
    ]
)

LAYER_SCHEMAS: dict[DataLayer, pa.Schema] = {
    DataLayer.RAW_MARKET_EVENTS: RAW_MARKET_EVENTS_SCHEMA,
    DataLayer.MARKET_STATE_SNAPSHOTS: MARKET_STATE_SNAPSHOTS_SCHEMA,
    DataLayer.FORWARD_CURVE: FORWARD_CURVE_SCHEMA,
    DataLayer.FORWARD_DIAGNOSTICS: FORWARD_DIAGNOSTICS_SCHEMA,
    DataLayer.IV_POINTS: IV_POINTS_SCHEMA,
    DataLayer.SURFACE_PARAMETERS: SURFACE_PARAMETERS_SCHEMA,
    DataLayer.SURFACE_GRID: SURFACE_GRID_SCHEMA,
    DataLayer.PRICING_RESULTS: PRICING_RESULTS_SCHEMA,
    DataLayer.POSITIONS: POSITIONS_SCHEMA,
    DataLayer.RISK_AGGREGATES: RISK_AGGREGATES_SCHEMA,
    DataLayer.SCENARIO_RESULTS: SCENARIO_RESULTS_SCHEMA,
    DataLayer.QC_RESULTS: QC_RESULTS_SCHEMA,
}


def schema_for_layer(layer: DataLayer) -> pa.Schema:
    if layer not in LAYER_SCHEMAS:
        raise KeyError(f"No parquet schema for layer: {layer}")
    return LAYER_SCHEMAS[layer]


def required_columns(layer: DataLayer) -> tuple[str, ...]:
    return tuple(schema_for_layer(layer).names)
