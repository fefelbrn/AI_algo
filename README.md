# Volatility Infrastructure Platform

Infrastructure de volatilité basée sur IBKR — projet M1 AI for Algorithmic Trading.

## Structure du monorepo

```
AI for algo/
├── guidelines/     # Roadmap, notes de cours, specs
├── frontend/       # Dashboard / UI (à venir)
├── backend/        # Code Python — connectivity, universe, pricing…
└── processes/      # Scripts ops, logs, artifacts, runbooks
```

## Statut

- **Step 1** — Access, environments, and security ✅
- **Step 2** — Instrument master and universe discovery ✅
- **Step 3** — Market-data ingestion (Parquet snapshots, option C) ✅
- **Step 4** — Persistent storage & data model ✅

## Démarrage rapide

```bash
# À la racine du repo
python3 -m venv .venv
source .venv/bin/activate
pip install -e "backend/[dev]"

# IB Gateway (paper, port 4002) doit être lancé
python processes/scripts/bootstrap_connectivity.py    # Step 1
python processes/scripts/discover_universe.py         # Step 2
python processes/scripts/run_collector.py             # Step 3
pytest backend/tests/ -v
```

## Documentation

| Dossier | Doc |
|---------|-----|
| `processes/docs/` | [environment.md](processes/docs/environment.md), [collector.md](processes/docs/collector.md) |
| `backend/docs/` | [universe.md](backend/docs/universe.md), [schemas.md](backend/docs/schemas.md) |
| `processes/docs/` | [storage.md](processes/docs/storage.md) — metadata & partitions |
| `guidelines/` | Roadmap industrielle (PDF local) |
