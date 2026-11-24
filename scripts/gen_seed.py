"""Generate scripts/seed.sql from src/cs_player/data/zywoo.json.

产出可重复执行的 INSERT 脚本：

    .venv\\Scripts\\python.exe -X utf8 scripts\\gen_seed.py
    mysql -h 127.0.0.1 -u root --default-character-set=utf8mb4 cs_legends < scripts\\seed.sql

脚本先按子表 → 父表顺序 DELETE，再插入，因此可反复执行。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 项目根目录
DATA_FILE = ROOT / "src" / "cs_player" / "data" / "zywoo.json"   # 数据文件路径
OUT_FILE = Path(__file__).resolve().parent / "seed.sql"   # 输出文件路径

# 与 src/cs_player/content.py 的 TAG_LABELS 保持一致
TAG_LABELS = {
    "major": "Major",
    "champion": "冠军",
    "mvp": "MVP",
    "milestone": "里程碑",
    "notable": "重要名次",
}

# 与 src/cs_player/static/js/map.js 的 ORGANIZER_META 保持一致
ORGANIZER_META = {
    "ESL": {"short": "ESL", "color": "#4f9cf9"},
    "BLAST": {"short": "BLAST", "color": "#f5c451"},
    "PGL": {"short": "PGL", "color": "#f472b6"},
    "StarLadder": {"short": "SL", "color": "#f87171"},
    "Beyond the Summit": {"short": "BTS", "color": "#34d399"},
    "FACEIT": {"short": "FACEIT", "color": "#fb923c"},
    "Epic Esports Events": {"short": "EPIC", "color": "#a78bfa"},
    "Gamers8 (Saudi Esports Federation)": {"short": "G8", "color": "#2dd4bf"},
}

# 已知英文名（其余留 NULL，需要时再补）
COUNTRY_EN = {"法国": "France"}
# 跨国赛区：不是真实国家，标为 region
REGIONS = {"欧洲赛区"}


def q(value: object) -> str:    # SQL字面值化函数
    """SQL literal."""
    if value is None:   # 处理 None 值
        return "NULL"
    if isinstance(value, bool):   # 处理布尔值
        return "1" if value else "0"
    if isinstance(value, (int, float)):   # 处理整数和浮点数
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "''")   # 处理字符串中的转义字符和单引号
    return f"'{text}'"


def qjson(value: object) -> str:    # JSON字面值化函数
    if value is None:   # 处理 None 值
        return "NULL"
    return q(json.dumps(value, ensure_ascii=False))


def insert_block(table: str, columns: list[str], rows: list[list[str]], chunk: int = 100) -> str:
    if not rows:    # 处理空表
        return f"-- {table}: 0 rows\n"
    head = f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n"   # 生成 INSERT 语句头
    out: list[str] = []
    for start in range(0, len(rows), chunk):     # 分块处理数据
        body = ",\n".join("  (" + ", ".join(row) + ")" for row in rows[start : start + chunk])  # 生成 VALUES 语句体
        out.append(head + body + ";\n") #完整的 INSERT 语句
    return "".join(out)


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))    # 读取 JSON文件
    player = data["player"]    # 提取选手数据
    stats = data["stats"]    # 提取选手统计数据
    events = sorted(data["events"], key=lambda e: (e["date"], e["id"]))    # 排序事件数据

    tournaments = [e for e in events if e.get("matches")]    # 筛选出有比赛的事件
    milestones = [e for e in events if not e.get("matches")]    # 筛选出无比赛的事件

    # ---- country -----------------------------------------------------------
    country_names = sorted({e["country"] for e in events} | {player["country_cn"]})    # 提取所有国家名称
    country_id = {name: i for i, name in enumerate(country_names, start=1)}    # 生成国家ID映射
    country_rows = [     # 生成国家数据行
        [str(country_id[n]), q(n), q(COUNTRY_EN.get(n)), q("region" if n in REGIONS else "country")]
        for n in country_names
    ]

    # ---- organizer ---------------------------------------------------------
    org_names = sorted({e["organizer"] for e in tournaments if e.get("organizer")})    # 提取所有主办方名称
    org_id = {name: i for i, name in enumerate(org_names, start=1)}    # 生成主办方ID映射
    org_rows = []
    for name in org_names:    # 生成主办方数据行
        meta = ORGANIZER_META.get(name, {})
        org_rows.append([str(org_id[name]), q(name), q(meta.get("short")), q(meta.get("color"))])

    # ---- player / player_stat ---------------------------------------------
    player_rows = [
        [
            q(player["id"]),
            q(player["nickname"]),
            q(player.get("name")),
            q(country_id[player["country_cn"]]),
            q(player.get("birth_date")),
            q(player.get("role")),
            q(player.get("team")),
            q(player.get("joined_team")),
            q(player.get("tagline")),
            q(player.get("bio")),
            qjson(player.get("accolades")),
            qjson(player.get("sources")),
        ]
    ]
    stat_rows = [
        [
            q(player["id"]),
            q(stats["major_titles"]),
            q(stats["major_mvps"]),
            q(stats["hltv_mvps"]),
            q(stats["grand_slams"]),
            q(stats["prize_money_usd"]),
            qjson(stats.get("hltv_top1_years")),
        ]
    ]

    # ---- tournament / appearance / tag / match ----------------------------
    tournament_rows: list[list[str]] = []
    appearance_rows: list[list[str]] = []
    appearance_tag_rows: list[list[str]] = []
    match_rows: list[list[str]] = []
    appearance_id = 0

    for event in tournaments:
        tournament_rows.append(
            [
                q(event["id"]),
                q(event["title"]),
                q(event["date"]),
                q(event.get("city") or None),
                q(event.get("venue") or None),
                q(country_id[event["country"]]),
                q(event.get("lat")),
                q(event.get("lng")),
                q(org_id[event["organizer"]] if event.get("organizer") else None),
                q(event.get("source") or None),
            ]
        )
        appearance_id += 1
        appearance_rows.append(
            [
                str(appearance_id),
                q(player["id"]),
                q(event["id"]),
                q(event["result"]),
                q(event.get("opponent")),
                q(event.get("score")),
                q(event.get("summary")),
            ]
        )
        for tag_index, tag in enumerate(event["tags"]):
            if tag == "milestone" or tag not in TAG_LABELS:
                continue
            appearance_tag_rows.append([str(appearance_id), q(tag), str(tag_index)])
        for seq, match in enumerate(event["matches"], start=1):
            match_rows.append(
                [
                    str(appearance_id),
                    str(seq),
                    q(match.get("stage") or None),
                    q(match["opponent"]),
                    q(match.get("score") or None),
                    q(match.get("result")),
                ]
            )

    tag_rows = [[q(code), q(label)] for code, label in TAG_LABELS.items()]

    milestone_rows = [
        [
            q(player["id"]),
            q(event["id"]),
            q(event["date"]),
            q(event["title"]),
            q(event.get("result")),
            q(event.get("city")),
            q(country_id[event["country"]]),
            q(event.get("venue") or None),
            q(event.get("summary")),
            q(event.get("source") or None),
        ]
        for event in milestones
    ]

    parts: list[str] = []
    parts.append("-- 由 scripts/gen_seed.py 自动生成，请勿手工编辑\n")
    parts.append("USE cs_legends;\nSET NAMES utf8mb4;\n\n")
    parts.append("DELETE FROM appearance_match;\n")
    parts.append("DELETE FROM appearance_tag;\n")
    parts.append("DELETE FROM appearance;\n")
    parts.append("DELETE FROM milestone;\n")
    parts.append("DELETE FROM player_stat;\n")
    parts.append("DELETE FROM tournament;\n")
    parts.append("DELETE FROM player;\n")
    parts.append("DELETE FROM tag;\n")
    parts.append("DELETE FROM organizer;\n")
    parts.append("DELETE FROM country;\n\n")
    parts.append(insert_block("country", ["id", "name_zh", "name_en", "kind"], country_rows))
    parts.append(insert_block("organizer", ["id", "name", "short_name", "color"], org_rows))
    parts.append(
        insert_block(
            "player",
            [
                "id", "nickname", "real_name", "country_id", "birth_date", "role", "team",
                "joined_team", "tagline", "bio", "accolades", "sources",
            ],
            player_rows,
        )
    )
    parts.append(
        insert_block(
            "player_stat",
            ["player_id", "major_titles", "major_mvps", "hltv_mvps", "grand_slams", "prize_money_usd", "hltv_top1_years"],
            stat_rows,
        )
    )
    parts.append(insert_block("tag", ["code", "label"], tag_rows))
    parts.append(
        insert_block(
            "tournament",
            ["id", "title", "event_date", "city", "venue", "country_id", "lat", "lng", "organizer_id", "source_note"],
            tournament_rows,
        )
    )
    parts.append(
        insert_block(
            "appearance",
            ["id", "player_id", "tournament_id", "placement", "opponent", "score", "summary"],
            appearance_rows,
        )
    )
    parts.append(insert_block("appearance_tag", ["appearance_id", "tag_code", "seq"], appearance_tag_rows))
    parts.append(
        insert_block(
            "appearance_match",
            ["appearance_id", "seq", "stage", "opponent", "score", "result"],
            match_rows,
        )
    )
    parts.append(
        insert_block(
            "milestone",
            ["player_id", "slug", "event_date", "title", "result", "city", "country_id", "venue", "summary", "source_note"],
            milestone_rows,
        )
    )

    OUT_FILE.write_text("".join(parts), encoding="utf-8", newline="\n")

    print(f"written {OUT_FILE}")
    print(
        f"country={len(country_rows)} organizer={len(org_rows)} player={len(player_rows)} "
        f"tournament={len(tournament_rows)} appearance={len(appearance_rows)} "
        f"tag={len(tag_rows)} appearance_tag={len(appearance_tag_rows)} "
        f"match={len(match_rows)} milestone={len(milestone_rows)}"
    )


if __name__ == "__main__":
    main()
