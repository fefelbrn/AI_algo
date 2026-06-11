# Forward curve — Step 6

Builds **forward prices** and **implied carry** from market-state snapshots.

## Methods (roadmap)

| Method | Source | Priority |
|--------|--------|----------|
| **future** | `role=future` snapshot at tenor | preferred (config) |
| **parity** | call/put mids: F = K + e^(rT)(C−P) | fallback / cross-check |
| **blended** | average future + parity | optional |

Default **r = 0** (`backend/configs/forwards.yaml`) — per prof notes.

## QC

- MAD outlier rejection on parity candidates
- Per-strike diagnostics persisted (`forward_diagnostics`)
- `forward_confidence`, `quality_label` on curve rows

## CLI

```bash
python processes/scripts/build_forwards.py --trade-date 2026-06-09
```

Requires Step 5 snapshots for the same date.

## Output

```
processes/artifacts/forward_curve/dt=2026-06-09/session_id=.../forwards.parquet
processes/artifacts/forward_diagnostics/dt=2026-06-09/session_id=.../forward_diagnostics.parquet
```

## Columns (curve)

`forward_price`, `tenor_label`, `tenor_distance_days`, `spot_price`, `implied_carry_rate`, `forward_method`, `forward_confidence`

## Next

**Step 7** — quote QC filter before IV inversion.
