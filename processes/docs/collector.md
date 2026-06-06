# Market Data Collector — Step 3

Snapshot collector (mode B) — option C universe → **Parquet**.

## Univers collecté (option C)

Par produit (**sp500**, **eurostoxx50**) :

| Rôle | Contenu |
|------|---------|
| **index** | SPX / ESTX50 (fallback SPY / FEZ si paper) |
| **future** | ES / FESX — 1 contrat par tenor (9 tenors) |
| **option** | ATM ±30δ proxy via bandes 0.90 / 1.00 / 1.10 × spot |

## Tenors

`10d | 1m | 3m | 6m | 9m | 12m | 18m | 24m | 36m`

Config : `backend/configs/collector.yaml` + `backend/configs/tenors.yaml`

## Lancer

```bash
source .venv/bin/activate
pip install -e "backend/[dev]"

# IB Gateway paper (port 4002) — client_id 1 pour collector
python processes/scripts/run_collector.py

# Test court (~1 snapshot puis stop)
python processes/scripts/run_collector.py --max-duration 320 --client-id 1
```

## Sortie Parquet

```
processes/artifacts/raw_market_events/
  dt=2026-06-09/
    session_id=20260609T140000Z/
      events_part_0000.parquet
      session_manifest.json
```

### Schéma event (1 row = 1 champ)

`event_id | session_id | snapshot_ts | instrument_key | product_name | role | field_name | field_value | receipt_ts | collector_ts | tenor_label | con_id`

## Critères Step 3

- [x] Append-only Parquet (pas JSON/CSV)
- [x] Timestamps `receipt_ts` + `collector_ts`
- [x] Snapshot toutes les 5 min
- [x] Session manifest avec diagnostics
- [x] Pas d'analytics dans le collector

## Suite

- **processes** : tenor tagger sur forwards (affichage frontend)
- **Step 5** : market-state snapshots depuis ce raw Parquet
