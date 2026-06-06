"""Path setup for process scripts."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def setup_import_path() -> None:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
