# Volatility Infrastructure Platform

Infrastructure de volatilité basée sur IBKR — projet M1 AI for Algorithmic Trading.

## Statut

- **Step 1** — Access, environments, and security ✅

## Démarrage rapide

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Lancer IB Gateway (paper, port 4002), puis :
python scripts/bootstrap_connectivity.py
```

Voir [docs/environment.md](docs/environment.md) pour le guide complet.

## Structure

```
configs/     # YAML — exchanges, instruments, calendars, QC, env
src/         # Code source (connectivity, …)
scripts/     # Entry points opérationnels
tests/       # Tests unitaires
docs/        # Runbooks
artifacts/   # Sorties bootstrap (gitignored)
logs/        # Logs (gitignored)
```
