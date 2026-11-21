"""SQLModel table models for the CS Legends MySQL schema.

These models mirror ``docs/db-schema.sql`` one-for-one (table names, column names,
MySQL types).  The SQL file stays the authoritative DDL for creating/recreating
the database; if you change a table here, change it there as well.

Only the read path is used by the current release, but the models are complete
enough for future writes (favourites, admin editing, more players).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Enum, String, Text
from sqlalchemy.dialects.mysql import BIGINT, DECIMAL, INTEGER, SMALLINT, TINYINT
from sqlmodel import Field, SQLModel

COUNTRY_KIND = Enum("country", "region", name="country_kind")
MATCH_RESULT = Enum("胜", "负", name="match_result")


class Country(SQLModel, table=True):
    """国家/地区字典。region 表示跨国赛区（如「欧洲赛区」）。"""

    __tablename__ = "country"

    id: int | None = Field(
        default=None,
        sa_column=Column("id", TINYINT(unsigned=True), primary_key=True, autoincrement=True),
    )
    name_zh: str = Field(sa_column=Column("name_zh", String(64), nullable=False, unique=True))
    name_en: str | None = Field(default=None, sa_column=Column("name_en", String(96)))
    kind: str = Field(default="country", sa_column=Column("kind", COUNTRY_KIND, nullable=False))


class Organizer(SQLModel, table=True):
    """赛事主办方字典，short_name / color 供地图标记使用。"""

    __tablename__ = "organizer"

    id: int | None = Field(
        default=None,
        sa_column=Column("id", TINYINT(unsigned=True), primary_key=True, autoincrement=True),
    )
    name: str = Field(sa_column=Column("name", String(96), nullable=False, unique=True))
    short_name: str | None = Field(default=None, sa_column=Column("short_name", String(16)))
    color: str | None = Field(default=None, sa_column=Column("color", String(7)))


class Player(SQLModel, table=True):
    """选手档案，id 即 slug（对应 data/<slug>.json 的文件名）。"""

    __tablename__ = "player"

    id: str = Field(sa_column=Column("id", String(32), primary_key=True))
    nickname: str = Field(sa_column=Column("nickname", String(64), nullable=False))
    real_name: str | None = Field(default=None, sa_column=Column("real_name", String(96)))
    country_id: int | None = Field(default=None, sa_column=Column("country_id", TINYINT(unsigned=True)))
    birth_date: date | None = Field(default=None, sa_column=Column("birth_date", Date))
    role: str | None = Field(default=None, sa_column=Column("role", String(32)))
    team: str | None = Field(default=None, sa_column=Column("team", String(96)))
    joined_team: date | None = Field(default=None, sa_column=Column("joined_team", Date))
    tagline: str | None = Field(default=None, sa_column=Column("tagline", String(160)))
    bio: str | None = Field(default=None, sa_column=Column("bio", Text))
    accolades: list[str] | None = Field(default=None, sa_column=Column("accolades", JSON))
    sources: list[str] | None = Field(default=None, sa_column=Column("sources", JSON))
    created_at: datetime | None = Field(default=None, sa_column=Column("created_at", DateTime))


class PlayerStat(SQLModel, table=True):
    """选手生涯统计，与 player 1:1。"""

    __tablename__ = "player_stat"

    player_id: str = Field(sa_column=Column("player_id", String(32), primary_key=True))
    major_titles: int = Field(default=0, sa_column=Column("major_titles", TINYINT(unsigned=True), nullable=False))
    major_mvps: int = Field(default=0, sa_column=Column("major_mvps", TINYINT(unsigned=True), nullable=False))
    hltv_mvps: int = Field(default=0, sa_column=Column("hltv_mvps", SMALLINT(unsigned=True), nullable=False))
    grand_slams: int = Field(default=0, sa_column=Column("grand_slams", TINYINT(unsigned=True), nullable=False))
    prize_money_usd: int = Field(default=0, sa_column=Column("prize_money_usd", BIGINT(unsigned=True), nullable=False))
    hltv_top1_years: list[int] | None = Field(default=None, sa_column=Column("hltv_top1_years", JSON))


class Tournament(SQLModel, table=True):
    """一届赛事。lat / lng 为 NULL 表示无法在地球上定位（线上赛等）。"""

    __tablename__ = "tournament"

    id: str = Field(sa_column=Column("id", String(64), primary_key=True))
    title: str = Field(sa_column=Column("title", String(160), nullable=False))
    event_date: date = Field(sa_column=Column("event_date", Date, nullable=False))
    city: str | None = Field(default=None, sa_column=Column("city", String(96)))
    venue: str | None = Field(default=None, sa_column=Column("venue", String(160)))
    country_id: int = Field(sa_column=Column("country_id", TINYINT(unsigned=True), nullable=False))
    lat: Decimal | None = Field(default=None, sa_column=Column("lat", DECIMAL(8, 5)))
    lng: Decimal | None = Field(default=None, sa_column=Column("lng", DECIMAL(8, 5)))
    organizer_id: int | None = Field(default=None, sa_column=Column("organizer_id", TINYINT(unsigned=True)))
    source_note: str | None = Field(default=None, sa_column=Column("source_note", String(160)))


class Appearance(SQLModel, table=True):
    """选手 × 赛事：一次参赛及其最终名次。"""

    __tablename__ = "appearance"

    id: int | None = Field(
        default=None,
        sa_column=Column("id", INTEGER(unsigned=True), primary_key=True, autoincrement=True),
    )
    player_id: str = Field(sa_column=Column("player_id", String(32), nullable=False))
    tournament_id: str = Field(sa_column=Column("tournament_id", String(64), nullable=False))
    placement: str | None = Field(default=None, sa_column=Column("placement", String(32)))
    opponent: str | None = Field(default=None, sa_column=Column("opponent", String(96)))
    score: str | None = Field(default=None, sa_column=Column("score", String(32)))
    summary: str | None = Field(default=None, sa_column=Column("summary", Text))


class Tag(SQLModel, table=True):
    """事件标签字典。"""

    __tablename__ = "tag"

    code: str = Field(sa_column=Column("code", String(16), primary_key=True))
    label: str = Field(sa_column=Column("label", String(32), nullable=False))


class AppearanceTag(SQLModel, table=True):
    """参赛-标签多对多。"""

    __tablename__ = "appearance_tag"

    appearance_id: int = Field(sa_column=Column("appearance_id", INTEGER(unsigned=True), primary_key=True))
    tag_code: str = Field(sa_column=Column("tag_code", String(16), primary_key=True))
    seq: int = Field(default=0, sa_column=Column("seq", TINYINT(unsigned=True), nullable=False))


class AppearanceMatch(SQLModel, table=True):
    """参赛记录中的逐场赛果。"""

    __tablename__ = "appearance_match"

    id: int | None = Field(
        default=None,
        sa_column=Column("id", INTEGER(unsigned=True), primary_key=True, autoincrement=True),
    )
    appearance_id: int = Field(sa_column=Column("appearance_id", INTEGER(unsigned=True), nullable=False))
    seq: int = Field(sa_column=Column("seq", TINYINT(unsigned=True), nullable=False))
    stage: str | None = Field(default=None, sa_column=Column("stage", String(64)))
    opponent: str = Field(sa_column=Column("opponent", String(96), nullable=False))
    score: str | None = Field(default=None, sa_column=Column("score", String(32)))
    result: str | None = Field(default=None, sa_column=Column("result", MATCH_RESULT))


class Milestone(SQLModel, table=True):
    """生涯里程碑：没有赛事与赛果的节点（出生、加入队伍等）。"""

    __tablename__ = "milestone"

    id: int | None = Field(
        default=None,
        sa_column=Column("id", INTEGER(unsigned=True), primary_key=True, autoincrement=True),
    )
    player_id: str = Field(sa_column=Column("player_id", String(32), nullable=False))
    slug: str = Field(sa_column=Column("slug", String(64), nullable=False))
    event_date: date = Field(sa_column=Column("event_date", Date, nullable=False))
    title: str = Field(sa_column=Column("title", String(160), nullable=False))
    result: str | None = Field(default=None, sa_column=Column("result", String(32)))
    city: str | None = Field(default=None, sa_column=Column("city", String(96)))
    country_id: int | None = Field(default=None, sa_column=Column("country_id", TINYINT(unsigned=True)))
    venue: str | None = Field(default=None, sa_column=Column("venue", String(160)))
    summary: str | None = Field(default=None, sa_column=Column("summary", Text))
    source_note: str | None = Field(default=None, sa_column=Column("source_note", String(160)))
