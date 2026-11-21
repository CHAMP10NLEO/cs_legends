-- CS Legends · MySQL 8.0 schema
-- 用法（在项目根目录）：
--   mysql -h 127.0.0.1 -u root --default-character-set=utf8mb4 < docs/db-schema.sql
-- 说明：
--   1) 本文件只建表，不灌数据；数据由 scripts/gen_seed.py 生成 scripts/seed.sql 后导入。
--   2) 全部表 utf8mb4 / utf8mb4_0900_ai_ci，与现有库一致。
--   3) 派生字段（date_label、has_coords、order/year、tag_labels）不入库，由查询/视图生成。
--   4) events 里的 84 条记录拆成两类：有 matches 的 82 条 → tournament + appearance；
--      无 matches 的 2 条（birth、join-vitality）→ milestone。

CREATE DATABASE IF NOT EXISTS cs_legends
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE cs_legends;

SET NAMES utf8mb4;

DROP VIEW IF EXISTS v_appearance;
DROP TABLE IF EXISTS appearance_match, appearance_tag, appearance, tournament,
                     milestone, player_stat, player, tag, organizer, country;

-- ---------------------------------------------------------------------------
-- 字典：国家/地区
-- 23 行 = 22 个真实国家 + 1 个「欧洲赛区」（两场线上赛的国家字段，kind='region'）
-- ---------------------------------------------------------------------------
CREATE TABLE country (
  id       TINYINT UNSIGNED AUTO_INCREMENT,
  name_zh  VARCHAR(64) NOT NULL COMMENT '中文名，与 zywoo.json 的 country 字段一致',
  name_en  VARCHAR(96) NULL     COMMENT '英文名，已知时填写',
  kind     ENUM('country','region') NOT NULL DEFAULT 'country'
           COMMENT 'country=真实国家；region=跨国赛区（如欧洲赛区）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_country_name_zh (name_zh)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='国家/地区字典';

-- ---------------------------------------------------------------------------
-- 字典：赛事主办方（11 行）
-- short_name / color 取自 static/js/map.js 的 ORGANIZER_META，缺省为 NULL
-- ---------------------------------------------------------------------------
CREATE TABLE organizer (
  id         TINYINT UNSIGNED AUTO_INCREMENT,
  name       VARCHAR(96) NOT NULL COMMENT 'JSON 中的 organizer 原文',
  short_name VARCHAR(16) NULL     COMMENT '地图标记上的缩写，如 ESL / BTS / G8',
  color      CHAR(7)     NULL     COMMENT '地图标记颜色 #rrggbb',
  PRIMARY KEY (id),
  UNIQUE KEY uk_organizer_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='赛事主办方字典';

-- ---------------------------------------------------------------------------
-- 选手：一人一行（当前只有 zywoo）
-- ---------------------------------------------------------------------------
CREATE TABLE player (
  id          VARCHAR(32) NOT NULL COMMENT 'slug，对应 PLAYER_FILES 的文件名，如 zywoo',
  nickname    VARCHAR(64) NOT NULL,
  real_name   VARCHAR(96) NULL,
  country_id  TINYINT UNSIGNED NULL,
  birth_date  DATE NULL,
  role        VARCHAR(32) NULL   COMMENT '场上位置，如 AWPer',
  team        VARCHAR(96) NULL   COMMENT '当前队伍',
  joined_team DATE NULL          COMMENT '加入当前队伍日期',
  tagline     VARCHAR(160) NULL,
  bio         TEXT NULL,
  accolades   JSON NULL          COMMENT '荣誉要点字符串数组',
  sources     JSON NULL          COMMENT '资料来源字符串数组',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_player_country (country_id),
  CONSTRAINT fk_player_country FOREIGN KEY (country_id) REFERENCES country (id)
    ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='选手基本信息';

-- ---------------------------------------------------------------------------
-- 选手生涯统计：与 player 1:1，分离存放避免选手档案被汇总数字污染
-- ---------------------------------------------------------------------------
CREATE TABLE player_stat (
  player_id       VARCHAR(32) NOT NULL,
  major_titles    TINYINT UNSIGNED  NOT NULL DEFAULT 0,
  major_mvps      TINYINT UNSIGNED  NOT NULL DEFAULT 0,
  hltv_mvps       SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  grand_slams     TINYINT UNSIGNED  NOT NULL DEFAULT 0,
  prize_money_usd BIGINT UNSIGNED   NOT NULL DEFAULT 0 COMMENT '生涯奖金（美元）',
  hltv_top1_years JSON NULL COMMENT 'HLTV 年度第一的年份数组，如 [2019,2020,2023,2025]',
  PRIMARY KEY (player_id),
  CONSTRAINT fk_stat_player FOREIGN KEY (player_id) REFERENCES player (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='选手生涯统计';

-- ---------------------------------------------------------------------------
-- 赛事：一届比赛一行（82 行）
-- lat/lng 为 NULL 表示该赛事不可在地球上定位（线上赛 / 无坐标）
-- ---------------------------------------------------------------------------
CREATE TABLE tournament (
  id           VARCHAR(64)  NOT NULL COMMENT '沿用 JSON 的事件 id，如 iem-katowice-2024',
  title        VARCHAR(160) NOT NULL,
  event_date   DATE NOT NULL COMMENT 'JSON 的 date（赛程结束日）',
  city         VARCHAR(96)  NULL,
  venue        VARCHAR(160) NULL,
  country_id   TINYINT UNSIGNED NOT NULL,
  lat          DECIMAL(8,5) NULL,
  lng          DECIMAL(8,5) NULL,
  organizer_id TINYINT UNSIGNED NULL,
  source_note  VARCHAR(160) NULL COMMENT 'JSON 的 source 原文',
  PRIMARY KEY (id),
  KEY idx_tournament_date (event_date),
  KEY idx_tournament_country (country_id),
  KEY idx_tournament_organizer (organizer_id),
  CONSTRAINT fk_tournament_country FOREIGN KEY (country_id) REFERENCES country (id)
    ON UPDATE CASCADE,
  CONSTRAINT fk_tournament_organizer FOREIGN KEY (organizer_id) REFERENCES organizer (id)
    ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='赛事（一届比赛）';

-- ---------------------------------------------------------------------------
-- 参赛：选手 × 赛事（82 行）。这是原 JSON 中 events[i] 的真身
-- placement 保留 JSON 的 result 原文（冠军 / 亚军 / 3–4 名 / 冠军 · MVP …）
-- ---------------------------------------------------------------------------
CREATE TABLE appearance (
  id            INT UNSIGNED AUTO_INCREMENT,
  player_id     VARCHAR(32) NOT NULL,
  tournament_id VARCHAR(64) NOT NULL,
  placement     VARCHAR(32) NULL COMMENT 'JSON 的 result 原文',
  opponent      VARCHAR(96) NULL COMMENT 'JSON 的事件级关键对手（不等于最后一场的对手）',
  score         VARCHAR(32) NULL COMMENT 'JSON 的事件级比分摘要（如 2-0 / 1-2）',
  summary       TEXT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_appearance_player_tournament (player_id, tournament_id),
  KEY idx_appearance_tournament (tournament_id),
  CONSTRAINT fk_appearance_player FOREIGN KEY (player_id) REFERENCES player (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_appearance_tournament FOREIGN KEY (tournament_id) REFERENCES tournament (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='选手在某届赛事的参赛记录';

-- ---------------------------------------------------------------------------
-- 标签字典（5 行）+ 参赛标签（70 行）
-- ---------------------------------------------------------------------------
CREATE TABLE tag (
  code  VARCHAR(16) NOT NULL COMMENT 'major / champion / mvp / notable / milestone',
  label VARCHAR(32) NOT NULL COMMENT '中文展示名，取自 content.py 的 TAG_LABELS',
  PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='事件标签字典';

CREATE TABLE appearance_tag (
  appearance_id INT UNSIGNED NOT NULL,
  tag_code      VARCHAR(16)  NOT NULL,
  seq           TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '标签在该事件中的原始顺序',
  PRIMARY KEY (appearance_id, tag_code),
  KEY idx_appearance_tag_code (tag_code),
  CONSTRAINT fk_at_appearance FOREIGN KEY (appearance_id) REFERENCES appearance (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_at_tag FOREIGN KEY (tag_code) REFERENCES tag (code)
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='参赛-标签多对多';

-- ---------------------------------------------------------------------------
-- 逐场赛果（398 行）。表名避开 MySQL 保留字 MATCH
-- ---------------------------------------------------------------------------
CREATE TABLE appearance_match (
  id            INT UNSIGNED AUTO_INCREMENT,
  appearance_id INT UNSIGNED NOT NULL,
  seq           TINYINT UNSIGNED NOT NULL COMMENT '该届赛事内的第几场，从 1 开始',
  stage         VARCHAR(64) NULL COMMENT 'JSON 的 stage，空串存 NULL（259 场无阶段名）',
  opponent      VARCHAR(96) NOT NULL,
  score         VARCHAR(32)  NULL,
  result        ENUM('胜','负') NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_match_appearance_seq (appearance_id, seq),
  CONSTRAINT fk_match_appearance FOREIGN KEY (appearance_id) REFERENCES appearance (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='参赛记录中的逐场赛果';

-- ---------------------------------------------------------------------------
-- 里程碑（2 行）：出生、加入 Team Vitality，这类记录没有赛事/赛果
-- ---------------------------------------------------------------------------
CREATE TABLE milestone (
  id          INT UNSIGNED AUTO_INCREMENT,
  player_id   VARCHAR(32) NOT NULL,
  slug        VARCHAR(64) NOT NULL COMMENT 'JSON 的事件 id，如 birth',
  event_date  DATE NOT NULL,
  title       VARCHAR(160) NOT NULL,
  result      VARCHAR(32) NULL COMMENT 'JSON 的 result，如 起点 / 启程',
  city        VARCHAR(96) NULL,
  country_id  TINYINT UNSIGNED NULL,
  venue       VARCHAR(160) NULL,
  summary     TEXT NULL,
  source_note VARCHAR(160) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_milestone_player_slug (player_id, slug),
  CONSTRAINT fk_milestone_player FOREIGN KEY (player_id) REFERENCES player (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_milestone_country FOREIGN KEY (country_id) REFERENCES country (id)
    ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='生涯里程碑';

-- ---------------------------------------------------------------------------
-- 便捷视图：一行 = 一次参赛 + 赛事 + 国家 + 主办方 + 坐标派生字段
-- 供核对数据 / 后续 content.py 切数据源时直接取用
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_appearance AS
SELECT
  a.id                                  AS appearance_id,
  a.player_id,
  a.placement,
  a.summary,
  t.id                                  AS tournament_id,
  t.title,
  t.event_date,
  t.city,
  t.venue,
  c.name_zh                             AS country_zh,
  c.name_en                             AS country_en,
  c.kind                                AS country_kind,
  o.name                                AS organizer,
  o.short_name                          AS organizer_short,
  o.color                               AS organizer_color,
  t.lat,
  t.lng,
  (t.lat IS NOT NULL AND t.lng IS NOT NULL) AS has_coords
FROM appearance a
JOIN tournament t ON t.id = a.tournament_id
JOIN country c    ON c.id = t.country_id
LEFT JOIN organizer o ON o.id = t.organizer_id;
