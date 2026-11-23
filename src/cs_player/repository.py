"""MySQL read layer built on SQLModel.

Every function returns plain dicts shaped exactly like the bundled JSON file,
so ``content.py`` can serve either source and the templates / map.js never know
the difference.

The connection string comes from :mod:`cs_player.config` — either
``CS_LEGENDS_DB_URL`` in the environment or a local ``.env`` file, e.g.

    mysql+pymysql://root:secret@127.0.0.1:3306/cs_legends?charset=utf8mb4
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import Engine, create_engine, select
from sqlmodel import Session

from .config import db_url, DB_URL_ENV
from .models import (
    Appearance,
    AppearanceMatch,
    AppearanceTag,
    Country,
    Milestone,
    Organizer,
    Player,
    PlayerStat,
    Tournament,
)

_engines: dict[str, Engine] = {}    # 缓存数据库引擎


def get_engine() -> Engine: 
    url = db_url()  # 获取数据库url
    if url is None:    # 如果url为空，抛出异常
        raise RuntimeError(f"{DB_URL_ENV} is not set")
    engine = _engines.get(url)  # 从缓存中获取数据库引擎      
    if engine is None:    # 如果缓存中没有数据库引擎，创建新的数据库引擎
        engine = create_engine(url, pool_pre_ping=True, future=True)
        _engines[url] = engine
    return engine   # 返回数据库引擎


def _tournament_date_label(value) -> str:   # 格式化tournament日期为year.month
    """Tournaments show year.month, milestones show the full date."""
    return value.strftime("%Y.%m")


def _first_player(session: Session, player_id: str | None) -> Player:
    stmt = select(Player).order_by(Player.id)   # 查询所有玩家，按id排序
    if player_id:   # 如果提供了玩家id，添加筛选条件
        stmt = stmt.where(Player.id == player_id)
    player = session.scalars(stmt).first()  # 查询第一个玩家
    if player is None:  # 如果没有查询到玩家，抛出异常
        raise LookupError(f"no player rows found for {player_id}")
    return player   # 返回查询到的玩家


def get_player(player_id: str | None = None) -> dict:
    with Session(get_engine()) as session:  #创建数据库会话
        player = _first_player(session, player_id)  # 查询选手
        country = session.get(Country, player.country_id) if player.country_id else None    # 获取选手国家信息
        return {
            "id": player.id,
            "nickname": player.nickname,
            "name": player.real_name,
            "country": (country.name_en or country.name_zh) if country else None,
            "country_cn": country.name_zh if country else None,
            "birth_date": player.birth_date.isoformat() if player.birth_date else None,
            "role": player.role,
            "team": player.team,
            "joined_team": player.joined_team.isoformat() if player.joined_team else None,
            "tagline": player.tagline,
            "bio": player.bio,
            "accolades": player.accolades,
            "sources": player.sources,
        }


def get_stats(player_id: str | None = None) -> dict:
    with Session(get_engine()) as session:  #创建数据库会话
        player = _first_player(session, player_id)  # 查询选手
        stat = session.get(PlayerStat, player.id)  # 查询选手统计信息
        if stat is None:  # 如果没有查询到选手统计信息，抛出异常
            raise LookupError(f"no player_stat row for {player_id}")
        return {
            "major_titles": stat.major_titles,
            "major_mvps": stat.major_mvps,
            "hltv_top1_years": stat.hltv_top1_years,
            "hltv_mvps": stat.hltv_mvps,
            "grand_slams": stat.grand_slams,
            "prize_money_usd": stat.prize_money_usd,
        }


def get_players() -> list[dict]:
    with Session(get_engine()) as session:  #创建数据库会话
        active_id = _first_player(session, None).id  # 查询第一个玩家，作为活跃玩家默认展示
        rows = session.exec(    # 查询所有玩家，包括国家信息
            select(Player, Country)
            .outerjoin(Country, Country.id == Player.country_id)
            .order_by(Player.id)
        ).all()
        return [    # 格式化查询结果，返回玩家列表
            {
                "id": player.id,
                "nickname": player.nickname,
                "team": player.team,
                "country_cn": country.name_zh if country else None,
                "active": player.id == active_id,
            }
            for player, country in rows
        ]


def get_events(player_id: str | None = None) -> list[dict]:
    """Return every event (tournaments + milestones) as JSON-shaped dicts."""
    with Session(get_engine()) as session:  # 创建数据库会话
        player = _first_player(session, player_id)  # 查询选手

        rows = session.exec(    # 查询所有选手的出现记录，包括 tournament、country、organizer
            select(Appearance, Tournament, Country, Organizer)
            .join(Tournament, Tournament.id == Appearance.tournament_id)
            .join(Country, Country.id == Tournament.country_id)
            .outerjoin(Organizer, Organizer.id == Tournament.organizer_id)
            .where(Appearance.player_id == player.id)
            .order_by(Tournament.event_date, Tournament.id)
        ).all()

        appearance_ids = [appearance.id for appearance, *_ in rows]  # 提取所有出现记录的id

        matches: dict[int, list[dict]] = defaultdict(list)  # 初始化比赛字典
        in_matches = session.exec(    # 查询所有选手的比赛记录
            select(AppearanceMatch)
            .where(AppearanceMatch.appearance_id.in_(appearance_ids))
            .order_by(AppearanceMatch.appearance_id, AppearanceMatch.seq)
        ).all()
        for match in in_matches:  # 遍历所有比赛记录
            matches[match.appearance_id].append(
                {
                    "stage": match.stage or "",
                    "opponent": match.opponent,
                    "score": match.score,
                    "result": match.result,
                }
            )

        tags: dict[int, list[str]] = defaultdict(list)  # 初始化标签字典
        in_tags = session.scalars(  # 查询所有选手的标签记录
            select(AppearanceTag)
            .where(AppearanceTag.appearance_id.in_(appearance_ids))
            .order_by(AppearanceTag.appearance_id, AppearanceTag.seq, AppearanceTag.tag_code)
        )
        for link in in_tags:  # 遍历所有标签记录
            tags[link.appearance_id].append(link.tag_code)

        events: list[dict] = [  # 格式化查询结果，返回事件列表
            {
                "id": tournament.id,
                "date": tournament.event_date.isoformat(),
                "date_label": _tournament_date_label(tournament.event_date),
                "title": tournament.title,
                "result": appearance.placement,
                "city": tournament.city,
                "country": country.name_zh,
                "venue": tournament.venue or "",
                "lat": float(tournament.lat) if tournament.lat is not None else None,
                "lng": float(tournament.lng) if tournament.lng is not None else None,
                "opponent": appearance.opponent,
                "score": appearance.score,
                "tags": tags[appearance.id],
                "summary": appearance.summary,
                "source": tournament.source_note or "",
                "organizer": organizer.name if organizer else "",
                "matches": matches[appearance.id],
            }
            for appearance, tournament, country, organizer in rows
        ]

        milestone_rows = session.exec(  # 查询所有选手的里程碑记录
            select(Milestone, Country)
            .outerjoin(Country, Country.id == Milestone.country_id)
            .where(Milestone.player_id == player.id)
            .order_by(Milestone.event_date, Milestone.slug)
        ).all()
        events.extend(  # 合并所有里程碑记录
            {
                "id": milestone.slug,
                "date": milestone.event_date.isoformat(),
                "date_label": milestone.event_date.strftime("%Y.%m.%d"),
                "title": milestone.title,
                "result": milestone.result,
                "city": milestone.city,
                "country": country.name_zh if country else None,
                "venue": milestone.venue or "",
                "lat": None,
                "lng": None,
                "opponent": None,
                "score": None,
                "tags": ["milestone"],
                "summary": milestone.summary,
                "source": milestone.source_note or "",
            }
            for milestone, country in milestone_rows
        )

        return events
