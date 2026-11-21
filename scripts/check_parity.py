"""Compare the payload built from zywoo.json with the payload built from MySQL.

    .venv\\Scripts\\python.exe -X utf8 scripts\\check_parity.py

Uses ``.env`` / ``CS_LEGENDS_DB_URL`` for the connection. Exit code 0 means both
sources produce identical JSON (dict order aside).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cs_player import config, content  # noqa: E402


def snapshot(source: str) -> dict:
    os.environ[config.SOURCE_ENV] = source
    content.reset_fallback()
    return {
        "player": content.get_player(),
        "stats": content.get_stats(),
        "players": content.get_players(),
        "events": content.public_events(content.get_events()),
    }


def diff(expected, actual, path: str = "") -> list[str]:
    """Return a short list of human-readable differences."""
    problems: list[str] = []
    if type(expected) is not type(actual):
        return [f"{path}: type {type(expected).__name__} != {type(actual).__name__}"]
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                problems.append(f"{path}.{key}: only in mysql")
            elif key not in actual:
                problems.append(f"{path}.{key}: only in json")
            else:
                problems += diff(expected[key], actual[key], f"{path}.{key}")
        return problems
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(expected)} != {len(actual)}"]
        for index, (left, right) in enumerate(zip(expected, actual)):
            problems += diff(left, right, f"{path}[{index}]")
        return problems
    if expected != actual:
        problems.append(f"{path}: {expected!r} != {actual!r}")
    return problems


def main() -> int:
    if config.db_url() is None:
        print(f"{config.DB_URL_ENV} is not set (no .env / environment variable)", file=sys.stderr)
        return 2

    from_json = snapshot("json")
    from_db = snapshot("db")
    os.environ.pop(config.SOURCE_ENV, None)

    problems = diff(from_json, from_db)
    print(f"events json={len(from_json['events'])} db={len(from_db['events'])}")
    if not problems:
        print("PARITY OK - JSON and MySQL payloads are identical")
        return 0

    print(f"PARITY FAILED - {len(problems)} difference(s), first 25:")
    for line in problems[:25]:
        print("  " + line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
