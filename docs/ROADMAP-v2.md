# CS Legends v2 开发路线图

> 基于当前目录中的 v1（ZywOo 单选手地图）制定。目标是把「一个选手的地图」扩展成「CS 历史的可交互编年史」。

## 0. 结论先行

1. **不要重写 v1。** 它已经解决了最难的两件事：全屏地图体验和账号会话。
2. **真正要改的是内容模型。** 现在一条 `event` 同时表示「赛事」和「某选手参加该赛事」，多选手会重复、无法互查。应拆成 `tournament`（赛事）+ `appearance`（参赛记录）+ `match`（单场）+ `chapter`（故事章节）。
3. **技术栈保持不变。** FastAPI + Jinja2 服务端渲染 + Globe.gl 2（Three.js）+ 原生 JS，不引入 React/Vue，不做前端构建。
4. **内容先继续用 JSON。** 可 diff、可 code review、可版本管理；用户和收藏继续用 SQLite。等出现非技术编辑，再考虑后台和 PostgreSQL。
5. **交付顺序：** 内容模型 → 多选手页面 → 全局三维地球/时间轴 → 故事化 → 账号增强 → 部署。

> **决策记录（2026-11-18）：** 地图方案确认为**三维地球**——Globe.gl 2 + Three.js + Natural Earth 国界数据，v1 已按此实现并验收。Leaflet / 瓦片地图方案作废，不再作为备选或后续版本目标。权威设计描述见 `docs/design-spec.md`（三维地球章节），接口见 `docs/api-contract.md`。

## 1. 现状盘点

### 1.1 已经有的

| 维度 | 现状 |
| --- | --- |
| 页面 | `/` 全屏三维地球（本期不含登录与个人页） |
| 数据 | `zywoo.json`：27 条生涯节点，25 条赛事，139 场逐场赛果 |
| 地图 | Globe.gl 三维地球 + Natural Earth 国家多边形；国家悬停高亮、单击固定右侧详情或底部抽屉 |
| 账号 | 本期无账号体系（代码已移除，后续版本重新引入） |
| API | `/api/health`、`/api/players/zywoo` |
| 设计 | 暗色、全屏、无照片，已有设计 Token 与响应式规范 |

### 1.2 关键限制

| 位置 | 问题 | 影响 |
| --- | --- | --- |
| `src/cs_player/content.py:12` | `PLAYER_FILES = ("zywoo.json",)` | 新增选手要改代码 |
| `src/cs_player/app.py:198` | `/api/players/zywoo` 硬编码 | 无法按 slug 取选手 |
| `src/cs_player/static/js/map.js:518` | 选择器只关闭菜单，不跳转 | 多选手入口是空壳 |
| `src/cs_player/data/zywoo.json` | 赛事字段和选手成绩混在一条 event | 同一赛事无法被多个选手复用 |
| 全局 | 没有测试、没有 git 提交、没有 CSRF | 重构风险高，公网部署不安全 |
| 环境 | `starlette.testclient` 需要 `httpx2`，当前未安装 | 现在无法写接口测试 |
| 工程 | `uv sync` 可能因旧 `.venv` 失败（见 `docs/STATUS.md`） | 新人拉项目起不来 |

### 1.3 结论

v1 是一个很好的**垂直切片**，但它是按「单选手、事件流」写的。v2 的重点不是加页面，而是把数据从「选手的事件列表」升级为「赛事库 + 选手参赛记录 + 故事章节」的三层结构。

## 2. 目标产品与 MVP

### 2.1 一句话

以世界地图为舞台、以时间轴为叙事线的 CS 传奇选手编年史：点开一位选手，看他的成长故事、职业轨迹和参加过的所有大赛；拖动时间轴，看一个时代如何在地图上亮起来。

### 2.2 三个核心体验

1. **地图即索引**：所有选手、所有赛事落在地图上；按年代、年份、选手、赛事级别筛选。
2. **选手即故事**：每位选手 5–7 个成长章节，章节绑定时间、地点、赛事；滚动阅读时地图跟随飞行。
3. **时间即脉络**：底部时间轴从 2001 拖到 2026，地图标记和事件流同步变化。

### 2.3 MVP 范围

| 项 | 目标 |
| --- | --- |
| 选手 | 6–8 位，覆盖 CS 1.6 / CS:GO / CS2 |
| 赛事 | 25–30 场，其中至少 15 场 Major |
| 地图 | 全局三维地球，年代/年份/选手筛选，国家标记聚合 |
| 选手页 | 档案、成长章节、战队履历、赛事时间线、荣誉 |
| 赛事页 | 日期、城市、场馆、主办方、奖金、冠军、参赛选手 |
| 时间轴 | 年份范围 + 事件密度 + 地图联动 |
| 账号 | 注册/登录/退出 + CSRF + 收藏选手/赛事 |
| 内容 | JSON schema + 校验脚本 + 单元测试 |

推荐首发名单（按时代和地区搭配）：

| 选手 | 国家 | 时代 | 代表队伍 | 故事钩子 |
| --- | --- | --- | --- | --- |
| ZywOo | 法国 | CS:GO / CS2 | Team Vitality | 天梯天才 → 三冠王 |
| s1mple | 乌克兰 | CS:GO | Natus Vincere | 争议天才 → Stockholm 巅峰 |
| dev1ce | 丹麦 | CS:GO | Astralis | 体系核心 → 四冠王朝 |
| NiKo | 波黑 | CS:GO / CS2 | FaZe / G2 | 顶级步枪手的转会与指挥转型 |
| FalleN | 巴西 | CS:GO | Luminosity / SK | 「Professor」与巴西 CS 崛起 |
| donk | 俄罗斯 | CS2 | Team Spirit | 新生代上海 Major |
| NEO | 波兰 | CS 1.6 | Virtus.pro | 老将主场 Katowice 2014 |

### 2.4 非目标

- 评论、点赞、用户投稿。
- OAuth、邮箱验证、找回密码。
- 原生 App、离线地图、VR/AR 地球。
- 全量赛事数据库（先精选，不做 HLTV 镜像）。
- 第一阶段不做 Web 后台（用 JSON + 校验脚本维护内容）。

## 3. 内容模型（最关键）

### 3.1 为什么要拆

现在一条 event 长这样：

```json
{
  "id": "paris-major-2023",
  "title": "BLAST.tv Paris Major 2023",
  "date": "2023-05-21",
  "city": "巴黎",
  "venue": "Accor Arena",
  "result": "冠军",
  "matches": []
}
```

它同时包含「赛事本身」（名称、日期、城市、场馆）和「ZywOo 在这届赛事的结果」（冠军、逐场比赛）。当 s1mple 也参加 Paris 2023 时：

- 赛事信息要复制一份，改一处漏一处；
- 无法回答「这届赛事有哪些选手参加」；
- 无法做「按赛事查选手」「按城市查所有赛事」。

所以拆成：

```
tournaments 1 ── N appearances N ── 1 players
appearances 1 ── N matches
players 1 ── N chapters
players N ── M teams（memberships 带起止时间）
```

### 3.2 文件结构

继续放在包内，避免打包路径变化：

```
src/cs_player/data/
  teams.json
  players/
    zywoo.json
    s1mple.json
  tournaments/
    blast-paris-major-2023.json
    pgl-stockholm-major-2021.json
```

### 3.3 赛事文件

`tournaments/blast-paris-major-2023.json`：

```json
{
  "id": "blast-paris-major-2023",
  "name": "BLAST.tv Paris Major 2023",
  "short_name": "Paris 2023",
  "tier": "major",
  "game": "csgo",
  "start_date": "2023-05-08",
  "end_date": "2023-05-21",
  "city": "巴黎",
  "country": "FR",
  "venue": "Accor Arena",
  "lat": 48.8384,
  "lng": 2.3786,
  "organizer": "BLAST",
  "prize_pool_usd": 1250000,
  "winner_team_id": "vitality",
  "description": "最后一届 CS:GO Major，也是巴黎首次举办 Major。",
  "source": "Liquipedia / BLAST 官方"
}
```

约定：

- `tier`：`major` / `premier` / `elite` / `other`。
- `game`：`cs16` / `csgo` / `cs2`。
- 线上赛 `lat`、`lng` 为 `null`，API 保留；不归属任何国家，不进入地球面板与主办方标记。
- `winner_team_id` 是战队，不是选手；选手的冠军身份来自 `appearance.placement == 1`，避免转会后的归属错误。

### 3.4 选手文件

`players/zywoo.json`：

```json
{
  "id": "zywoo",
  "nickname": "ZywOo",
  "name": "Mathieu Herbaut",
  "country": "FR",
  "country_cn": "法国",
  "birth_date": "2000-11-09",
  "role": "AWPer",
  "era": "csgo",
  "tagline": "The Chosen One",
  "bio": "法国 AWPer……",
  "accolades": ["4× HLTV 年度第一", "3× Major 冠军 + 3× Major MVP"],
  "chapters": [
    {
      "id": "zywoo-start",
      "date": "2018-10-08",
      "age": 17,
      "title": "被 Vitality 选中",
      "body": "18 岁的 ZywOo 被 Team Vitality 招入……",
      "place": "巴黎",
      "lat": 48.8566,
      "lng": 2.3522,
      "tournament_id": null,
      "image": null,
      "quote": "他像是为这个游戏而生。"
    }
  ],
  "appearances": [
    {
      "tournament_id": "blast-paris-major-2023",
      "team_id": "vitality",
      "placement": 1,
      "result_label": "冠军",
      "prize_usd": 500000,
      "is_mvp": true,
      "matches": [
        {"stage": "传奇组瑞士轮", "opponent": "G2", "score": "16-13", "result": "胜"},
        {"stage": "决赛", "opponent": "GamerLegion", "score": "2-0", "result": "胜"}
      ]
    }
  ]
}
```

约定：

- `chapters` 按日期排序；`tournament_id` 可以为空（出生、转会、退役等）。
- `appearances` 只放「这位选手确实参加了」的赛事；不参加的赛事不写。
- `placement` 用整数：1、2、3–4、5–8、9–11、17–32；无法归入时用 `result_label`。
- `is_mvp` 表示该届 MVP；不要用 tag 表达。
- `matches` 只属于该选手在该届的比赛，按时间正序；`score` 在 BO1 用地图比分，BO3/BO5 用系列赛比分。
- 统计字段（Major 数、MVP 数、Top1 年份）**从数据推导**，不要像 v1 那样手写 `stats`，否则一定漂移。特殊记录（奖金总额等）可以放 `stats_override`。

### 3.5 战队文件

`teams.json`：

```json
[
  {"id": "vitality", "name": "Team Vitality", "country": "FR", "logo": null},
  {"id": "navi", "name": "Natus Vincere", "country": "UA", "logo": null}
]
```

选手的战队履历用 `memberships` 表达（`team_id`、`joined_at`、`left_at`、`role`），不要只存一个 `team` 字段，否则无法还原「什么时候在哪个队」。

### 3.6 从 v1 迁移

写一个一次性脚本 `scripts/migrate_v1.py`：

1. 读 `zywoo.json` 的 27 条 event。
2. `tags` 含 `milestone` 且没有 `matches` 的 2 条 → `chapters`。
3. 其余 25 条 → 生成 `tournaments/*.json`，按 `title + 年份` 去重；`result`、`opponent`、`score`、`matches` → `appearances`。
4. 手工补 `tier`、`game`、`winner_team_id`、`start_date`、`end_date`、`prize_pool_usd`。
5. 迁移后用校验脚本对比：25 条赛事、139 场比赛、坐标数量不变。

这一步不要交给「自动推断」；`tier` 和冠军必须人工确认，否则历史数据会错。

### 3.7 校验脚本

`scripts/validate_content.py`，用 Pydantic 模型校验并在启动时调用：

- ID 唯一、slug 合法；
- 日期 ISO 格式，`end_date >= start_date`；
- `lat` 在 [-90, 90]，`lng` 在 [-180, 180]；
- `appearance.tournament_id`、`team_id` 必须存在；
- `chapters.tournament_id` 存在或为 null；
- 同一选手同一赛事不能重复；
- `placement` 与 `result_label` 至少有一个；
- 冠军战队必须在参赛战队集合里（能校验时）；
- 所有 `source` 非空。

校验失败时开发环境直接启动失败；生产环境至少打 error 日志并拒绝热更新。

## 4. 技术方案

### 4.1 保持现有栈

| 层 | 选择 | 理由 |
| --- | --- | --- |
| Web | FastAPI + Jinja2 SSR | 内容站需要 SEO；现有页面可复用 |
| 地图 | Globe.gl 2（Three.js）+ Natural Earth 国界 GeoJSON | v1 已验证；CDN 引入，无构建步骤；不要为地图引入 React |
| 交互 | 原生 ES Modules | 无构建步骤，部署简单 |
| 内容 | JSON + Pydantic 校验 | 可 diff、可 review、可回滚 |
| 账号/收藏 | SQLite；需要时上 SQLAlchemy + Alembic | 写少读多，单机足够 |
| 部署 | Uvicorn + Caddy + Docker | 静态资源、HTTPS、反代一次搞定 |

**地图方案（2026-11-18 确认，替代 Leaflet）：**

- 渲染：Globe.gl 2（Three.js），jsDelivr CDN 引入，无前端构建步骤。
- 底图：`src/cs_player/static/data/countries.geojson`（Natural Earth，177 个 feature），按国家多边形分块，由 `polygonsData` 承载。
- 交互：国家悬停高亮（`polygonCapColor` 等 accessor + 重新赋值触发重绘）；右侧面板（移动端底部抽屉）展示该国赛事；单击固定面板，点海洋 / `×` / Esc 取消。
- 标记：`htmlElementsData` + `htmlElement` 渲染主办方徽标，每国一枚、列出该国全部主办方（按届数降序），做背面裁剪与屏幕空间去重。
- 性能：国家多边形只加载一次；筛选时更新 data 与 accessor，不重建 Globe 实例。

如果未来出现「非技术编辑要在线改内容」「多实例部署」「评论/投稿」，再切 PostgreSQL + SQLAlchemy + 后台。不要在 MVP 前做。

### 4.2 内容仓库层

新增 `src/cs_player/repository.py`（或改造 `content.py`）：

- 启动时加载 `teams.json`、`players/*.json`、`tournaments/*.json`；
- 建立索引：`players_by_id`、`tournaments_by_id`、`appearances_by_player`、`appearances_by_tournament`；
- 计算派生数据：每位选手的 Major 数、MVP 数、赛事年份列表、地图事件；
- 开发环境按文件 mtime 失效缓存，改 JSON 不用重启；
- 对外只暴露 `get_player(slug)`、`list_players()`、`get_tournament(slug)`、`map_events(filters)` 等函数，路由不直接读文件。

### 4.3 页面

| 路径 | 内容 |
| --- | --- |
| `/` | 全局三维地球 + 年代/年份/选手筛选 + 底部时间轴 |
| `/players` | 选手墙：按时代、国家、战队筛选 |
| `/players/{slug}` | 选手故事页：档案 + 章节 + 地图 + 履历 + 荣誉 |
| `/tournaments` | 赛事列表：按年份、级别、地区筛选 |
| `/tournaments/{slug}` | 赛事详情：信息 + 地图 + 参赛选手 + 赛果 |
| `/timeline` | 编年史：按年代分组的纵向时间线 |
| `/login` `/me` | 登录注册、个人页与收藏 |
| `/admin`（P1） | 内容管理，非 MVP |

### 4.4 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/players` | 选手列表，支持 `era`、`country`、`q` |
| GET | `/api/players/{slug}` | 档案 + 章节 + 参赛记录 + 派生统计 |
| GET | `/api/tournaments` | 赛事列表，支持 `era`、`year`、`tier`、`region` |
| GET | `/api/tournaments/{slug}` | 赛事 + 参赛选手 + 赛果 |
| GET | `/api/map` | 轻量地图事件：`era`、`from`、`to`、`player` |
| GET | `/api/timeline` | 年份桶 + 事件密度 |
| GET | `/api/search` | 选手/赛事/城市联合搜索 |
| POST/DELETE | `/api/favorites` | 收藏/取消收藏（需登录 + CSRF） |
| GET | `/api/me/favorites` | 我的收藏 |

地图接口只返回地球需要的字段（`id`、`name`、`date`、`city`、`country`、`lat`、`lng`、`tier`、`winner`、`player_ids`），**不要带 matches**。`country` 是地球按国家聚合的依据，不能省。详情在悬停/点击时再请求，控制首屏体积。

### 4.5 前端状态

所有筛选收口到一个 state：

```js
const state = {
  era: "all",        // all | cs16 | csgo | cs2
  from: 2001,
  to: 2026,
  player: null,      // slug
  selectedEvent: null
};
```

- 每次变化只做两件事：重算可见事件、更新地球数据；
- 状态同步到 URL：`/?era=csgo&from=2012&to=2023&player=zywoo`；
- 用 `history.replaceState`，支持刷新恢复和分享；
- 筛选在客户端完成（数据量 < 500 条），不要每个滑块都打接口。

## 5. 功能清单

### P0（MVP，必须）

- [ ] 全局三维地球：所有选手的赛事聚合到国家标记；年代、年份、选手筛选；放大后按城市展开；详情面板。
- [ ] 选手页：档案、5–7 个成长章节、战队履历、赛事时间线、荣誉、地图轨迹。
- [ ] 赛事页：日期、城市、场馆、主办方、奖金、冠军、参赛选手、逐场赛果。
- [ ] 时间轴：年份范围、事件密度、与地图联动、播放模式。
- [ ] 账号：注册/登录/退出；CSRF；登录限流；收藏选手/赛事；`/me` 展示收藏。
- [ ] 内容：Pydantic 校验、迁移脚本、派生统计、错误页。
- [ ] 测试：内容校验单测、路由/鉴权/收藏集成测试。

### P1（上线前尽量）

- [ ] 搜索（选手、赛事、城市）。
- [ ] 选手对比（同年代两位选手的赛事/荣誉并排）。
- [ ] 分享卡片（OG image，按选手/赛事生成）。
- [ ] 中英双语（至少赛事名和选手名保留英文）。
- [ ] `/admin` 或 CLI 导入（CSV/JSON）。
- [ ] 站点地图、结构化数据、RSS/更新日志。

### P2（以后）

- 评论/点赞、用户投稿、OAuth、邮箱验证、音频故事、离线 PWA。

## 6. 阶段计划

| 阶段 | 目标 | 主要任务 | 产出 | 预估 |
| --- | --- | --- | --- | --- |
| 0 | 基线 | git 提交 v1；修 `.venv`；装 `httpx2`；跑通启动与 3 条冒烟测试 | 可回滚的 v1 标签 | 0.5–1 天 |
| 1 | 内容模型 | 定 schema；迁移 ZywOo；新增 s1mple；校验脚本；派生统计 | `data/players/*`、`data/tournaments/*`、`validate_content.py` | 3–4 天 |
| 2 | 多选手页面 | 选手/赛事路由；选择器跳转；选手页；赛事页；API 按 slug | `/players/{slug}`、`/tournaments/{slug}` | 3–4 天 |
| 3 | 全局三维地球 | `/api/map` 接口；年代/年份筛选；标记去重与城市展开；URL 状态；详情懒加载 | 新版 `/` | 4–6 天 |
| 4 | 时间轴与故事 | 底部时间轴；播放模式；选手页 scrollytelling；生涯飞线 | 时间轴组件、故事页 | 3–4 天 |
| 5 | 账号增强 | CSRF；登录限流；收藏表；`/me`；权限字段 | 安全的账号体系 | 2–3 天 |
| 6 | 上线 | SEO/OG；响应式/可达性；性能；Docker/Caddy；备份 | 可访问站点 | 2–3 天 |

总计约 18–25 个工作日（单人）。内容研究是瓶颈：每位选手的资料的核对、写 5–7 段故事、补赛事元数据，通常要 1–2 天，建议与开发并行。

**MVP 截断线：** 阶段 0–3 + 基础收藏 = 10–14 天。先上线「多选手地图 + 选手页 + 赛事页」，时间轴和 scrollytelling 可以第二批。

## 7. 关键实现细节

### 7.1 地球与时间轴联动

- 时间轴用原生 `input[type=range]` 双滑块或自定义 SVG；年份刻度 2001–2026。
- `input` 事件做 80ms 防抖，只更新 data 与 accessor，不重建 Globe 实例。
- 标记按 `date` 过滤后重新设置 `globe.htmlElementsData(visible)`；多边形用颜色 accessor 读取闭包变量，改完重新赋值触发重绘。
- 播放模式：每 700–900ms 前进一年；鼠标悬停暂停；`prefers-reduced-motion` 下禁用动画。
- 年份变化时给新出现的标记加一次 300ms 的 pulse class，不要全量重绘。

### 7.2 标记聚合与去重

v1 已经解决「赛事一多图标互相叠字」：

- 每国一枚标记，列出该国全部主办方徽标（按届数降序，同业多届显示届数角标）；
- 背面国家用「球面点 × 相机位置」点乘裁剪；正面标记做屏幕空间矩形碰撞，重叠者淡出，按赛事总数优先保留；
- 相机 `change` 事件 140ms 防抖 + 400ms 轮询兜底，不逐帧重算。

v2 赛事量上升后：

- 同一国家多城市时按 `city` 分组，低视角只显示国家标记 + 数量徽标；
- 点击国家标记：`pointOfView` 飞到该城市（`altitude` 约 1.2），展开单赛事标记；
- 放大后标记自然分开，不需要引入 clustering 插件。

### 7.3 选手故事页（scrollytelling）

- 桌面：左侧章节滚动，右侧 sticky 地球；移动端地球在上、章节在下。
- `IntersectionObserver` 监听章节进入视口 60%；触发 `globe.pointOfView({ lat, lng, altitude: 1.6 }, 1000)`，并高亮对应国家或标记。
- 每个章节：年份、年龄、标题、120–200 字、一句引语、相关赛事链接、可选图片。
- 章节结束放「完整赛事列表」和「荣誉」，不要把所有内容都塞进滚动叙事。
- 尊重 `prefers-reduced-motion`：关闭飞行动画，直接 `pointOfView({ lat, lng, altitude }, 0)`。

### 7.4 生涯飞线

- 用 Globe.gl 的 `arcsData` + `arcStartLat` / `arcStartLng` / `arcEndLat` / `arcEndLng` 绘制，把选手有坐标的赛事按时间排序后依次连成弧线；
- 用 `arcDashLength` / `arcDashGap` / `arcDashAnimateTime` 做流动效果，不要自己写 canvas 动画；
- 点击章节时只高亮对应段，不要一次画 20 条线；
- 飞线是氛围，不是主信息；默认关闭，提供「查看生涯轨迹」开关。

### 7.5 账号与 CSRF

- 继续用 `SessionMiddleware`，不要改成 localStorage JWT。
- 登录后生成 `csrf_token` 存 session；所有 POST 表单带 hidden input；服务端 `hmac.compare_digest` 校验。
- 登录成功轮换 session；`SameSite=Lax`、`HttpOnly`；生产 `Secure`。
- 登录限流：同一 IP + 用户名 15 分钟 5 次失败；可以用 `slowapi`，也可以先用内存字典。
- 收藏表：`favorites(user_id, kind, ref_id, created_at)`，唯一约束 `(user_id, kind, ref_id)`；toggle 接口返回最新状态。
- 角色：`users.role`（`user` / `admin`），后台路由用依赖注入校验。

### 7.6 性能

- 国家 GeoJSON 约 839KB（177 个 feature），必须开 gzip；它只加载一次，不随筛选变化。
- 现状把事件与 matches 一起内嵌在 `#map-events`；v2 改为 `/api/map` 只返回坐标级字段、详情懒加载，首屏 JSON 控制在 150KB 以内。
- 开启 `GZipMiddleware`；静态资源加 `Cache-Control: max-age=31536000, immutable`（带 hash 文件名）或至少 7 天。
- 图片用 `loading="lazy"` + `srcset`；没有图片就用渐变/单色块，不要空 `<img>`。
- SQLite 开 WAL；用户查询加索引；内容用内存缓存。

### 7.7 SEO

- 选手页/赛事页服务端渲染，`<title>`、`description`、 canonical。
- OG image：`/og/player/{slug}.png` 用 Pillow 动态生成（名字 + 国家 + 主要荣誉），或预生成静态图。
- `sitemap.xml`、`robots.txt`；赛事页加 `SportsEvent` JSON-LD（可选）。

## 8. 数据与版权

这是这类站点最容易忽略、但最不能出错的部分。

| 来源 | 能怎么用 | 注意 |
| --- | --- | --- |
| Liquipedia | 事实、赛程、名次；API 可查 | 内容 CC BY-SA 3.0：署名 + 链接；不要整段翻译/复制描述，用自己的话写 |
| HLTV | 人工核对事实 | 禁止爬虫；不要批量抓取 |
| Wikipedia / Wikidata | 生平、基础事实 | CC BY-SA；署名 |
| 赛事官方（ESL/BLAST/PGL/StarLadder） | 日期、场馆、奖金、赛果 | 以官方为准；保留 `source` |
| 选手照片 | 默认不用 | 版权归摄影师/选手；除非有明确授权，否则用插画、剪影、字母头像 |
| 战队 Logo | 谨慎 | 商标权；非商业粉丝项目也不等于免许可 |
| 地球底图 | Natural Earth 国界（公有领域） | 已随包内置 `countries.geojson`；若改用卫星纹理或第三方瓦片，需另查署名与商用条款 |

写入规范：

- 每条赛事、每个章节都有 `source`；
- 站点页脚保留「数据来源 + 最后核对日期 + 非商业声明」；
- 不要复制 HLTV/Liquipedia 的段落，只取事实，用中文重写；
- 如果未来加图片，建立 `credits` 字段，记录作者、许可证、链接。

## 9. 测试与部署

### 9.1 测试

- `httpx2` 加入 dev 依赖（Starlette TestClient 需要）。
- 单元：内容校验、派生统计、日期/坐标边界。
- 集成：`/players/{slug}` 200/404、筛选参数、登录/登出、CSRF 拒绝、收藏幂等。
- E2E（Playwright，3 条即可）：地球加载并渲染国家与主办方图标；悬停国家出信息、单击后固定；登录后收藏并出现在 `/me`。
- CI：`ruff check` + `pytest` + `python scripts/validate_content.py`。

### 9.2 部署

- `Dockerfile`：`python:3.14-slim`，非 root 用户，`uvicorn` 启动。
- `docker-compose.yml`：`web` + `caddy`；`data/` 挂 volume；Caddy 负责 HTTPS 和静态缓存。
- 环境变量：`CS_LEGENDS_SECRET`、`CS_LEGENDS_DB`、`CS_LEGENDS_HTTPS_ONLY=1`。
- 备份：每天 `sqlite3 data/cs_legends.db ".backup ..."`，保留 7–30 天。
- 监控：`/api/health` + UptimeRobot；错误用 Sentry（可选）。
- 迁移：SQLite schema 变更用 Alembic 或简单的 `user_version` 迁移；不要手改生产库。

## 10. 本周行动清单

- [ ] `git add -A && git commit -m "chore: baseline v1"`，打 tag `v1.0`。
- [ ] 写 `docs/content-schema.md`，把第 3 节的 JSON 约定固化成 Pydantic 模型。
- [ ] 迁移 ZywOo：25 条赛事 → `tournaments/`，2 条里程碑 → `chapters`，139 场 → `appearances.matches`。
- [ ] 新增 s1mple 作为第二位选手，验证「同一赛事被多人引用」不会重复。
- [ ] 实现 `/players/{slug}` 和选择器跳转，先不做时间轴。
- [ ] 加 `scripts/validate_content.py` 和 3 条 pytest。
- [ ] 决策：首发 6–8 位选手的最终名单，以及每人 5–7 个章节的标题。

完成这 7 项，v2 的地基就有了；之后再接全局三维地球和时间轴，不会返工。
