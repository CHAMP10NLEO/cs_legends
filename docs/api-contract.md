# 接口契约（v1）

Base URL：`http://127.0.0.1:8000`
页面接口返回 HTML；数据接口返回 JSON，所有接口均为只读。

## 1. 健康检查

`GET /api/health`

```json
{ "status": "ok", "source": "db" }
```

`source` 为本次进程实际使用的数据源：`db`（MySQL，默认）或 `json`（数据库不可达或显式设置 `CS_LEGENDS_DATA_SOURCE=json` 时的兜底）。

## 2. 选手档案与事件

`GET /api/players/zywoo`

响应 200：

```json
{
  "player": {
    "id": "zywoo",
    "nickname": "ZywOo",
    "name": "Mathieu Herbaut",
    "country": "France",
    "country_cn": "法国",
    "birth_date": "2000-11-09",
    "role": "AWPer",
    "team": "Team Vitality",
    "joined_team": "2018-10-08",
    "tagline": "The Chosen One",
    "bio": "……"
  },
  "stats": {
    "major_titles": 3,
    "major_mvps": 3,
    "hltv_top1_years": [2019, 2020, 2023, 2025],
    "hltv_mvps": 34,
    "grand_slams": 2,
    "prize_money_usd": 2348734
  },
  "events": [
    {
      "id": "paris-major-2023",
      "date": "2023-05-21",
      "date_label": "2023.05",
      "title": "BLAST.tv Paris Major 2023",
      "result": "冠军",
      "organizer": "BLAST",
      "city": "巴黎",
      "country": "法国",
      "venue": "Accor Arena",
      "lat": 48.8384,
      "lng": 2.3786,
      "opponent": "GamerLegion",
      "score": "2-0",
      "matches": [
        { "stage": "传奇组瑞士轮", "opponent": "G2", "score": "16-13", "result": "胜" },
        { "stage": "传奇组瑞士轮", "opponent": "ENCE", "score": "16-13", "result": "胜" },
        { "stage": "传奇组瑞士轮", "opponent": "Monte", "score": "2-0", "result": "胜" },
        { "stage": "四分之一决赛", "opponent": "Into the Breach", "score": "2-0", "result": "胜" },
        { "stage": "半决赛", "opponent": "Apeks", "score": "2-0", "result": "胜" },
        { "stage": "决赛", "opponent": "GamerLegion", "score": "2-0", "result": "胜" }
      ],
      "tags": ["major", "champion", "mvp"],
      "tag_labels": [
        { "key": "major", "label": "Major" },
        { "key": "champion", "label": "冠军" },
        { "key": "mvp", "label": "MVP" }
      ],
      "summary": "在主场巴黎捧起生涯第一座 Major，并当选 Major MVP。",
      "source": "Liquipedia / HLTV"
    }
  ]
}
```

- `events` 按 `date` 正序，共 84 条（82 条赛事 + 2 条里程碑），赛果截至 2026-11-15。
- `lat`/`lng` 为 `null` 表示线上赛；线上赛与里程碑不参与国家聚合，不出现在地球的国家面板中。
- `organizer` 为赛事主办方；82 条赛事事件均有值。
- `matches` 为该选手在本届赛事参加的全部比赛，按时间正序；`stage` 为中文阶段名，`score` 为系列赛比分（BO1 使用地图比分），`result` 为 `胜` / `负`。
- `tags` 取值：`major`、`champion`、`mvp`、`milestone`、`notable`。
- `tag_labels` 是 `tags` 的展示映射，元素为 `{ key, label }`：`key` 同 `tags`，`label` 为中文文案。未知标签会被忽略，因此两个数组长度可能不一致；前端应直接遍历 `tag_labels`。
- 响应与数据源无关：**MySQL 是主数据源**（`CS_LEGENDS_DB_URL` / `.env`），数据库不可达时回退到内置 JSON；两种模式的 JSON 输出逐字节一致（见 `scripts/check_parity.py`）。
- 缓存出来的数据一律当只读用，要改就先拷贝一份。

## 3. 账号接口

OAuth2 **密码模式**：浏览器用表单 + HttpOnly Cookie，API 客户端用 bearer 令牌。除注册、登录、刷新外，账号接口都需要登录态；`/api/players/zywoo` 等公开只读接口**不需要**登录。

| 方法 · 路径 | 用途 | 成功 | 失败 |
| --- | --- | --- | --- |
| `GET /login` | 登录页 | 200 HTML；已登录时 303 跳到 `next` | — |
| `POST /auth/login` | 表单登录（`username`/`password`/`csrf_token`/`next`） | 303 → `next`，写 `access_token` + `refresh_token` Cookie | 401 密码错；429 限流；403 CSRF |
| `GET /register` | 注册页 | 200 HTML | — |
| `POST /auth/register` | 表单注册（`email`/`username`/`password`/`password_confirm`/`csrf_token`） | 303 → `/login?registered=1` | 409 重名；422 校验失败；403 CSRF |
| `POST /auth/token` | OAuth2 密码模式（`username` 可填邮箱或用户名） | 200 见下 | 401 `WWW-Authenticate: Bearer`；429 限流 |
| `POST /auth/refresh` | 轮换刷新令牌（Cookie 或 body `refresh_token`） | 200 新令牌对 | 401 无效 / 过期 / 重放 |
| `POST /auth/logout` | 退出当前设备（表单，需 `csrf_token`） | 303 → `/`，清 Cookie | 403 CSRF |
| `GET /account` | 账号页 | 200 HTML | 未登录 303 → `/login?next=/account` |
| `GET /api/me` | 当前账号（Bearer 或 Cookie） | 200 见下 | 401 |

`POST /auth/token` 与 `POST /auth/refresh` 的响应体：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "Yb3k... (opaque, 43 chars)",
  "token_type": "bearer",
  "expires_in": 900
}
```

`GET /api/me` 的响应体：

```json
{
  "id": 1,
  "email": "you@example.com",
  "username": "you",
  "display_name": "you",
  "role": "user",
  "created_at": "2026-11-25T08:00:00",
  "last_login_at": "2026-11-25T16:00:00"
}
```

约定：

- **access token**：JWT HS256，`sub` 用户 id、`jti`、`iat`、`exp`、`ver`（= `app_user.token_version`）、`typ=access`；15 分钟。`ver` 不匹配即视为已吊销。
- **refresh token**：不透明随机串，7 天；服务端只存 sha256，每次刷新轮换。已轮换的令牌被再次使用时，该用户整条令牌链撤销且 `token_version + 1`（所有 access token 立即失效）。
- **Cookie**：`access_token`（`Path=/`）、`refresh_token`（`Path=/auth`）、`csrf_token`（非 HttpOnly）；均 `SameSite=Lax`，生产环境加 `Secure`。
- **CSRF**：表单 POST 必须带隐藏字段 `csrf_token`，值与 `csrf_token` Cookie 一致；Bearer 客户端免 CSRF。
- **限流**：同一 identifier 或同一 IP，15 分钟内失败 5 次后返回 429（记录在 `login_attempt` 表）。
- **错误文案**：登录失败统一「邮箱或密码不正确」，不区分账号不存在与密码错误。
- 目前只做登录态，没有收藏 / 评论接口；没有邮箱验证与找回密码。

表结构见 `docs/auth-schema.sql`，完整链路自检见 `scripts/check_auth.py`。
