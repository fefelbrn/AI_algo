# Market-state snapshots — Step 5

Transforms **raw Parquet events** (Step 3) into aligned **market-state snapshots**.

## Reference spot logic

Priority (configurable in `backend/configs/snapshots.yaml`):

1. **mid** — bid/ask valid, spread ≤ threshold
2. **last** — fallback, `flag_fallback=true`
3. **carry_forward** — last trusted mid/last in session

Never hidden: `reference_type` column always set.

## CLI

```bash
# After collector has written raw events for a date
python processes/scripts/build_snapshots.py --trade-date 2026-06-09

# Single session
python processes/scripts/build_snapshots.py --trade-date 2026-06-09 --session-id 20260609T140000Z
```

## Output

```
processes/artifacts/market_state_snapshots/
  dt=2026-06-09/
    session_id=.../
      snapshots.parquet
      session_manifest.json
```

## Acceptance (roadmap Step 5)

- [x] Same raw + config → identical rows (deterministic)
- [x] Fallbacks labeled (`reference_type`, `flag_fallback`)
- [x] Stale quotes flagged (`flag_stale`, `quote_age_seconds`)
- [x] Pure builder (no IBKR in builder)
- [x] Same code path for live replay

## Next

**Step 6** — forward curve from snapshots (parity, tenor tagging).
