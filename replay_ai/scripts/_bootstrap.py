"""Make ``src`` importable when scripts are run directly from this directory.

Running ``python scripts/foo.py`` puts ``scripts/`` on ``sys.path``, not the
project root, so ``import src...`` fails. Importing this module first fixes the
path, and also makes ``scripts`` itself importable so scripts can share helpers.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
