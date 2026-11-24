"""Load and prepare player content.

MySQL is the primary, authoritative source (see :mod:`cs_player.repository`).
The bundled JSON file is the fallback when MySQL is unreachable and the seed used
to populate the database. Both paths produce the same dicts, so ``app.py``,
templates and ``map.js`` never need to know where the data came from.
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from . import config, repository

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "zywoo.json"
PLAYER_FILES = ("zywoo.json",)

TAG_LABELS = {
    "major": "Major",
    "champion": "冠军",
    "mvp": "MVP",
    "milestone": "里程碑",
    "notable": "重要名次",
}

#: 数据库出错后，多少秒内不再重试、直接读 JSON。
RETRY_SECONDS = 30.0

_retry_at = 0.0
_missing_url_warned = False
_fallback_warned = False


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def using_db() -> bool:
    """True when reads go to MySQL right now."""
    return (
        config.data_source() == "db"
        and config.db_url() is not None
        and time.monotonic() >= _retry_at
    )


def current_source() -> str:
    """``"db"`` or ``"json"`` — the source the next read will hit."""
    return "db" if using_db() else "json"


def reset_fallback() -> None:
    """Forget a recorded MySQL failure (used by ``scripts/check_parity.py``)."""
    global _retry_at
    _retry_at = 0.0


def _read(db_reader: Callable[[], Any], json_reader: Callable[[], Any]) -> Any:
    """Read from MySQL, falling back to the bundled JSON when it is unavailable."""
    global _retry_at, _missing_url_warned, _fallback_warned

    if not using_db():
        if config.data_source() == "db" and config.db_url() is None and not _missing_url_warned:
            _missing_url_warned = True
            log.warning(
                "未配置 %s（也没有 .env），改用内置 JSON；参考 .env.example",
                config.DB_URL_ENV,
            )
        return json_reader()

    try:
        return db_reader()
    except SQLAlchemyError as exc:
        _retry_at = time.monotonic() + RETRY_SECONDS
        if not _fallback_warned:
            _fallback_warned = True
            detail = str(exc).splitlines()[0][:200] if str(exc) else exc.__class__.__name__
            log.warning("MySQL 不可用（%s），%.0f 秒内改用内置 JSON", detail, RETRY_SECONDS)
        return json_reader()


def get_player() -> dict[str, Any]:
    return _read(repository.get_player, lambda: _load()["player"])


def get_stats() -> dict[str, Any]:
    return _read(repository.get_stats, lambda: _load()["stats"])


def get_players() -> list[dict[str, Any]]:
    def from_json() -> list[dict[str, Any]]:
        active_id = get_player()["id"]
        players: list[dict[str, Any]] = []
        for filename in PLAYER_FILES:
            path = DATA_DIR / filename
            if path == DATA_FILE:
                player = _load()["player"]
            else:
                with path.open("r", encoding="utf-8") as handle:
                    player = json.load(handle)["player"]
            players.append(
                {
                    "id": player["id"],
                    "nickname": player["nickname"],
                    "team": player["team"],
                    "country_cn": player["country_cn"],
                    "active": player["id"] == active_id,
                }
            )
        return players

    return _read(repository.get_players, from_json)


def get_events() -> list[dict[str, Any]]:
    """Every event (tournaments + milestones), sorted and decorated for templates."""
    events = _read(repository.get_events, lambda: _load()["events"])
    events = sorted(events, key=lambda event: (event["date"], event["id"]))

    prepared: list[dict[str, Any]] = []
    for event in events:
        item = dict(event)
        item["tag_labels"] = [
            {"key": tag, "label": TAG_LABELS[tag]} for tag in item["tags"] if tag in TAG_LABELS
        ]
        item["has_coords"] = item["lat"] is not None and item["lng"] is not None
        item["organizer"] = item.get("organizer") or ""
        item["matches"] = item.get("matches") or []
        prepared.append(item)
    return prepared


def public_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip template-only fields before returning JSON."""
    hidden = {"has_coords"}
    return [{key: value for key, value in event.items() if key not in hidden} for event in events]
