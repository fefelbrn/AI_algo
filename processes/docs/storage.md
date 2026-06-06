# Storage platform — Step 4

## Quick reference

```python
from src.storage import StoragePlatform, DataLayer

platform = StoragePlatform.open(artifacts_dir)

# Write validated parquet + register partition
platform.write_parquet_partition(
    DataLayer.FORWARD_CURVE,
    rows,
    trade_date="2026-06-09",
    filename="forwards.parquet",
    run_id="forward_job_001",
    product="sp500",
    source_layers=[("raw_market_events", "dt=2026-06-09/session_id=...")],
)

# Query metadata
platform.metadata.list_partitions("raw_market_events", "2026-06-09")
```

## On disk

```
processes/artifacts/
  metadata/platform.db       # jobs, partitions, lineage, schema registry
  raw_market_events/         # Step 3
  market_state_snapshots/    # Step 5 (empty until built)
  forward_curve/             # Step 6
  ...
  instrument_master/master.db  # Step 2
```

## Acceptance Step 4

- [x] All layer schemas defined (PyArrow)
- [x] Metadata SQLite for jobs + partitions + lineage
- [x] Unified partition paths
- [x] Write-ahead validation
- [x] Retention policy documented
- [x] Live collector registers jobs via platform

## Retention (config)

See `backend/configs/storage.yaml` — tiers 1–3, enforced manually for now.
