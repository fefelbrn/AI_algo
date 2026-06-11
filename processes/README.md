# Processes

Scripts opérationnels, runbooks, logs et artifacts runtime.

## Scripts

| Script | Step | Description |
|--------|------|-------------|
| `scripts/bootstrap_connectivity.py` | 1 | Smoke test IBKR |
| `scripts/discover_universe.py` | 2 | Découverte instrument master |
| `scripts/run_collector.py` | 3 | Collector snapshots → Parquet |
| `scripts/build_snapshots.py` | 5 | Raw events → market-state snapshots |
| `scripts/build_forwards.py` | 6 | Snapshots → forward curve + carry |

```bash
# depuis la racine du repo, venv activé
python processes/scripts/bootstrap_connectivity.py
python processes/scripts/discover_universe.py --client-id 2
```

## Runtime (gitignored)

```
processes/logs/       # logs des jobs
processes/artifacts/  # bootstrap JSONL, SQLite instrument master
```

## Documentation ops

Voir [docs/environment.md](docs/environment.md).
