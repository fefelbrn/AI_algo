# Instrument Master — Step 2

Canonical instrument master for underlyings, expiries, strikes, and multipliers.

## API

```python
from src.universe.master import InstrumentMaster

master = InstrumentMaster.from_config(config_dir, artifacts_dir, adapter=adapter)

# Discover from IBKR and persist
snapshot = master.discover_and_persist(session_date=date.today())

# Load stored universe
universe = master.load_active_universe("2026-06-06")

# Helpers
underlying = master.get_underlying("SPY", "2026-06-06")
chain = master.get_option_chain("SPY", "20260620", "2026-06-06")
contract = master.resolve_contract(instrument_key, "2026-06-06")
```

## CLI

```bash
# IB Gateway must be running (paper, port 4002)
source .venv/bin/activate
python scripts/discover_universe.py
```

Options:
- `--session-date YYYY-MM-DD` — date de session (défaut: aujourd'hui)
- `--client-id 2` — client ID dédié au service universe (voir `configs/instruments.yaml`)

## Configuration

| Fichier | Rôle |
|---------|------|
| `configs/instruments.yaml` | Liste des underlyings à découvrir |
| `configs/universe.yaml` | Fenêtre de maturité, batch size, filtres |

### Fenêtre de maturité (défaut)

- Min : 1 jour
- Max : 90 jours
- Cap : 2000 contrats par underlying (sécurité dev)

## Stockage

```
artifacts/instrument_master/
  master.db                              # SQLite — tables canoniques
  dt=2026-06-06/
    raw_broker_universe_v0.1.0_xxx.jsonl # Réponses brutes IBKR
    manifest_universe_v0.1.0_xxx.json    # Résumé + QC
```

## Instrument key

Format stable :
```
symbol|sec_type|exchange|currency|expiry|strike|right|multiplier|con_id
```

Exemple SPY call :
```
SPY|OPT|SMART|USD|20260620|500.000000|C|100.0000|12345
```

## Critères d'acceptation Step 2

- [ ] Même univers reproductible sur runs répétés (même date + config)
- [ ] Doublons supprimés de façon déterministe
- [ ] `multiplier` et `currency` toujours renseignés
- [ ] Contrats non résolus → exception `UnresolvedContractError` avec diagnostics
- [ ] Payloads bruts broker persistés pour audit

## Dépannage

| Symptôme | Action |
|----------|--------|
| 0 options | Vérifier `max_maturity_days` et la date de session |
| Timeout qualification | Réduire `max_contracts_per_underlying` dans `universe.yaml` |
| `clientId in use` | Utiliser `--client-id 2` (pas 10 du bootstrap) |
