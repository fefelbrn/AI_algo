"""Repository layout helpers."""

from pathlib import Path


def repo_root() -> Path:
    """Monorepo root (parent of backend/, processes/, frontend/)."""
    return Path(__file__).resolve().parents[2]


def backend_root() -> Path:
    return Path(__file__).resolve().parents[1]
