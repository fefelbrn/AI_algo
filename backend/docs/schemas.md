# Data schemas — Step 4

Platform schema version: **1.2.0**

Metadata DB: `processes/artifacts/metadata/platform.db`

## Partition layout

```
processes/artifacts/{layer}/dt={YYYY-MM-DD}/[underlying={sym}/][product={name}/][session_id={id}/]*.parquet
```

| Layer | Partition keys | Mutable |
|-------|----------------|---------|
| `raw_market_events` | dt, session_id | append-only |
| `market_state_snapshots` | dt, underlying | versioned replace |
| `forward_curve` | dt, product | versioned replace |
| `iv_points` | dt, underlying | versioned replace |
| `surface_*` | dt, product | versioned replace |
| `pricing_results` | dt | versioned replace |
| `risk_aggregates` | dt | versioned replace |
| `scenario_results` | dt | versioned replace |
| `qc_results` | dt | append |
| `instrument_master` | SQLite `master.db` | versioned |

## Raw market events (Step 3)

See `RAW_MARKET_EVENTS_SCHEMA` in `backend/src/storage/schemas.py`.

## Market state snapshots (Step 5)

| Column | Description |
|--------|-------------|
| reference_price / reference_type | mid, last, carry_forward, missing |
| spread_pct | (ask-bid)/mid × 100 |
| quote_age_seconds | snapshot_ts − exchange/receipt ts |
| flag_stale / flag_fallback | QC flags per roadmap |
| role / tenor_label | index, future, option + tenor bucket |

## Derived layers (Steps 5+)

Schemas defined in `backend/src/storage/schemas.py` — empty partitions allowed until pipelines run.

## Lineage rules

1. Raw layer is **never overwritten**
2. Derived partitions carry `source_snapshot_ts` + metadata lineage rows
3. Recompute derived = new `version_id`, raw unchanged
4. Job manifests in `job_runs` table

## Schema evolution

- Bump `PLATFORM_SCHEMA_VERSION` for breaking changes (Category A)
- `validate_rows()` rejects unknown columns by default
- See `backend/configs/storage.yaml` retention tiers
