"""Static guards for the approved layering: pages -> services -> repositories -> SQLite."""

import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_FILES = [ROOT / "app.py", *sorted((ROOT / "pages").glob("*.py"))]
FORBIDDEN_UI_IMPORTS = ("sqlite3", "mednexa.core.db", "mednexa.repositories", "pandas.io.sql")
SQL_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in (
    r"\bSELECT\b[^\n]{0,200}\bFROM\b", r"\bINSERT\s+INTO\b", r"\bUPDATE\s+\w+\s+SET\b",
    r"\bDELETE\s+FROM\b", r"\bCREATE\s+(TABLE|VIEW|INDEX)\b", r"\bexecute\s*\(")]


def _imports(path: Path) -> set[str]:
    mods = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
            mods |= {f"{node.module}.{a.name}" for a in node.names}
    return mods


def test_pages_do_not_touch_the_database():
    for f in UI_FILES:
        bad = [m for m in _imports(f) if m.startswith(FORBIDDEN_UI_IMPORTS)]
        assert not bad, f"{f.name} imports {bad}"


def test_pages_contain_no_sql():
    for f in UI_FILES:
        text = f.read_text(encoding="utf-8")
        hits = [p.pattern for p in SQL_PATTERNS if p.search(text)]
        assert not hits, f"{f.name}: {hits}"


def test_services_and_core_do_not_import_streamlit():
    for folder in ("services", "repositories", "core", "db"):
        for f in (ROOT / "mednexa" / folder).glob("*.py"):
            assert not any(m.startswith("streamlit") for m in _imports(f)), f"{folder}/{f.name}"


def test_repositories_are_only_used_by_services():
    for f in [*(ROOT / "mednexa" / "ui").glob("*.py"), *UI_FILES]:
        assert not any(m.startswith("mednexa.repositories") for m in _imports(f)), f.name


def test_config_is_single_source_for_brand_colours():
    from mednexa import config
    tokens = {v.upper() for v in config.THEME.values()}
    for f in [*(ROOT / "mednexa").rglob("*.py"), *UI_FILES]:
        if f.name == "config.py":
            continue
        text = f.read_text(encoding="utf-8").upper()
        leaked = [t for t in tokens if t in text]
        assert not leaked, f"{f.relative_to(ROOT)} hard-codes {leaked}"


def test_streamlit_theme_file_mirrors_config():
    """Streamlit needs .streamlit/config.toml; it must stay identical to config.THEME."""
    from mednexa import config
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert theme["base"] == "dark"
    assert theme["primaryColor"] == config.THEME["primary"]
    assert theme["backgroundColor"] == config.THEME["bg"]
    assert theme["secondaryBackgroundColor"] == config.THEME["surface"]
    assert theme["textColor"] == config.THEME["text"]
