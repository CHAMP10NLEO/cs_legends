"""Runtime configuration: where the data comes from.

MySQL is the primary, authoritative source. The connection string is read from
``CS_LEGENDS_DB_URL``; a local ``.env`` file in the project root (or the current
directory) is loaded first, so ``uv run`` works without exporting anything.

Set ``CS_LEGENDS_DATA_SOURCE=json`` to pin the bundled JSON file instead — handy
for offline demos, tests and comparisons.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_URL_ENV = "CS_LEGENDS_DB_URL"
SOURCE_ENV = "CS_LEGENDS_DATA_SOURCE"

_ENV_FILES = (PROJECT_ROOT / ".env", Path.cwd() / ".env")
_env_loaded = False


def load_env_files() -> None:
    """Load ``.env`` files once, never overriding real environment variables."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True

    seen: set[Path] = set()
    for candidate in _ENV_FILES:
        try:
            path = candidate.resolve()
        except OSError:  # pragma: no cover - unreadable cwd
            continue
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:  # pragma: no cover - permissions
            print(f"[config] cannot read {path}: {exc}", file=sys.stderr)
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def data_source() -> str:
    """``"db"`` (default) or ``"json"`` when explicitly pinned."""
    load_env_files()
    return "json" if os.environ.get(SOURCE_ENV, "").strip().lower() == "json" else "db"


def db_url() -> str | None:
    """MySQL connection string, or ``None`` when the JSON source is pinned."""
    if data_source() == "json":
        return None
    load_env_files()
    return os.environ.get(DB_URL_ENV, "").strip() or None
