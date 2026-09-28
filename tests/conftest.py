"""Shared test setup. The app database path points at a temp location that does not exist,
so Milestone 1 tests exercise the 'database not initialised' path deterministically."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["MEDNEXA_DB_PATH"] = str(Path(tempfile.gettempdir()) / "mednexa_m1_absent.db")
Path(os.environ["MEDNEXA_DB_PATH"]).unlink(missing_ok=True)
