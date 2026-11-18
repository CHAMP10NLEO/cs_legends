"""Load and prepare player content from the bundled JSON data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

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

FILTERS = [
    {"key": "all", "label": "全部"},
    {"key": "major", "label": "Major"},
    {"key": "champion", "label": "冠军"},
    {"key": "mvp", "label": "MVP"},
    {"key": "milestone", "label": "里程碑"},
]


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_player() -> dict[str, Any]:
    return _load()["player"]


def get_stats() -> dict[str, Any]:
    return _load()["stats"]


def get_players() -> list[dict[str, Any]]:
    active_id = get_player()["id"]
    players: list[dict[str, Any]] = []
    for filename in PLAYER_FILES:
        with (DATA_DIR / filename).open("r", encoding="utf-8") as handle:
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


def get_events() -> list[dict[str, Any]]:
    events = sorted(_load()["events"], key=lambda item: item["date"])
    prepared: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        item = dict(event)
        item["order"] = index + 1
        item["year"] = int(item["date"][:4])
        item["tag_labels"] = [TAG_LABELS[tag] for tag in item["tags"] if tag in TAG_LABELS]
        item["has_coords"] = item["lat"] is not None and item["lng"] is not None
        item["organizer"] = item.get("organizer") or ""
        item["matches"] = item.get("matches") or []
        prepared.append(item)
    return prepared


def group_by_year(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for event in events:
        if not groups or groups[-1]["year"] != event["year"]:
            groups.append({"year": event["year"], "events": []})
        groups[-1]["events"].append(event)
    return groups


def public_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip template-only fields before returning JSON."""
    hidden = {"order", "year", "tag_labels", "has_coords"}
    return [{key: value for key, value in event.items() if key not in hidden} for event in events]
