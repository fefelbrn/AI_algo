# Backend

Code Python de l'infrastructure de volatilité.

## Contenu

```
backend/
├── configs/    # YAML — env, instruments, universe, QC
├── src/        # Packages Python (connectivity, universe, …)
├── tests/      # Tests unitaires
└── docs/       # Documentation technique API
```

## Installation

```bash
# depuis la racine du repo
pip install -e "backend/[dev]"
```

## Tests

```bash
pytest backend/tests/ -v
```
