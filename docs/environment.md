# Environment setup — Step 1

Guide de mise en place pour la connectivité IBKR (roadmap Step 1).

## Prérequis

1. **Compte IBKR** (paper trading recommandé pour le développement)
2. **IB Gateway** ou **Trader Workstation (TWS)** installé localement
3. **Python 3.11+**

## Ports IBKR par défaut

| Mode | Application | Port |
|------|-------------|------|
| Paper | IB Gateway | **4002** |
| Paper | TWS | **7497** |
| Live | IB Gateway | 4001 |
| Live | TWS | 7496 |

Le fichier `configs/dev.yaml` utilise le port **4002** (Gateway paper).

## Installation

```bash
cd "/Users/fefe/Desktop/Cours M1 Albert/Semestre 2/AI for algo"

# Créer un venv (recommandé)
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -e ".[dev]"
# ou : pip install -r requirements.txt
```

## Configuration IB Gateway / TWS

Avant de lancer le bootstrap :

1. Ouvrir **IB Gateway** (ou TWS) et se connecter en **Paper Trading**
2. Aller dans **Configure → Settings → API → Settings**
3. Cocher **Enable ActiveX and Socket Clients**
4. Décocher **Read-Only API** si vous voulez tester les ordres plus tard (Step 1 reste en readonly)
5. Ajouter `127.0.0.1` dans **Trusted IP addresses** si demandé
6. Vérifier le port socket (4002 pour Gateway paper)

## Secrets et variables d'environnement

```bash
cp .env.example .env
# Éditer .env si besoin — ne jamais committer .env
```

| Variable | Défaut | Description |
|----------|--------|-------------|
| `IBKR_HOST` | 127.0.0.1 | Hôte Gateway/TWS |
| `IBKR_PORT` | 4002 | Port socket |
| `IBKR_CLIENT_ID` | 10 | ID client API |

### Convention client_id

| Service | client_id | Fichier |
|---------|-----------|---------|
| Collector (Step 3) | 1 | `configs/instruments.yaml` |
| Analytics (futur) | 2 | idem |
| Replay (futur) | 3 | idem |
| Bootstrap / smoke test | 10 | `configs/dev.yaml` |

**Ne jamais lancer deux services avec le même `client_id` sur la même session Gateway.**

## Smoke test (bootstrap)

```bash
source .venv/bin/activate
python scripts/bootstrap_connectivity.py
```

Le script doit afficher :
- l'état de session IBKR
- l'heure UTC
- la résolution du contrat SPY
- un quote bid/ask/last
- les health checks
- le chemin du fichier JSONL écrit dans `artifacts/bootstrap/`

Code de sortie :
- `0` — succès (ou warnings si marché fermé)
- `1` — échec de connexion ou health check critique

## Health checks

| Check | Critère |
|-------|---------|
| `api_reachable` | Connexion socket active |
| `login_valid` | Comptes managés visibles |
| `clock_sync` | Décalage horloge < 5s vs serveur IBKR |
| `market_data_entitlement` | Quote reçu pour SPY (warn si marché fermé) |

## Arborescence des logs et artifacts

```
logs/
  bootstrap_YYYYMMDD.log

artifacts/
  bootstrap/
    bootstrap_YYYYMMDDTHHMMSSZ.jsonl
```

## Reproduire l'environnement sur une nouvelle machine

1. Cloner le repo
2. Installer Python 3.11+
3. `python3 -m venv .venv && source .venv/bin/activate`
4. `pip install -e ".[dev]"`
5. Installer IB Gateway, activer l'API
6. `cp .env.example .env` (ajuster le port si TWS)
7. `python scripts/bootstrap_connectivity.py`

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `Connection refused` | Gateway/TWS pas lancé | Démarrer Gateway, vérifier le port |
| `clientId already in use` | Autre script connecté | Changer `IBKR_CLIENT_ID` ou fermer l'autre session |
| `No managed accounts` | Login incomplet | Reconnecter Gateway |
| Quote vide (warn) | Marché fermé / données différées | Normal hors heures de marché US |

## Critères d'acceptation Step 1

- [ ] Nouvelle machine provisionnée depuis cette doc
- [ ] Bootstrap script réussit
- [ ] Aucun secret dans le repo
- [ ] Config chargée via YAML + env vars
- [ ] Job exécutable sans intervention manuelle (hors démarrage Gateway)
