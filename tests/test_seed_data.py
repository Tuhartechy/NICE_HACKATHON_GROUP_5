"""Seed CSVs are exact, untouched copies of the validated source datasets."""

import hashlib
import subprocess
import sys
from pathlib import Path

from mednexa import config

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed"


def test_all_seed_files_present():
    assert sorted(p.name for p in SEED.glob("*.csv")) == sorted(config.SEED_FILES)


def test_seed_files_match_recorded_checksums():
    recorded = dict(reversed(line.split()) for line in (SEED / "CHECKSUMS.sha256").read_text().splitlines())
    assert set(recorded) == set(config.SEED_FILES)
    for name, digest in recorded.items():
        assert hashlib.sha256((SEED / name).read_bytes()).hexdigest() == digest, name


def test_both_validators_pass_on_seed_copies():
    for script in ("validate_data.py", "validate_product_data.py"):
        res = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout[-800:]
        assert "OVERALL: PASS" in res.stdout


def test_seed_builds_database_with_all_gates(tmp_path):
    import os
    env = {**os.environ, "MEDNEXA_DB_PATH": str(tmp_path / "seed.db")}
    res = subprocess.run([sys.executable, "-m", "mednexa.db.seed", "--reset"], cwd=ROOT, capture_output=True,
                         text=True, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "All seed checks passed." in res.stdout and "follow_ups_pending     48" in res.stdout
