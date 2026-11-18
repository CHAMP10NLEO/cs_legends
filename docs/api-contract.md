# 接口契约（v1）

Base URL：`http://127.0.0.1:8000`
页面接口返回 HTML；数据接口返回 JSON。除登录/注册外均为只读。

## 1. 健康检查

`GET /api/health`

```json
{ "status": "ok" }
```

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
      "summary": "在主场巴黎捧起生涯第一座 Major，并当选 Major MVP。",
      "source": "Liquipedia / HLTV"
    }
  ]
}
```

- `events` 按 `date` 正序。
- `lat`/`lng` 为 `null` 表示线上赛；线上赛与里程碑不参与国家聚合，不出现在地球的国家面板中。
- `organizer` 为赛事主办方；25 条赛事事件均有值。
- `matches` 为该选手在本届赛事参加的全部比赛，按时间正序；`stage` 为中文阶段名，`score` 为系列赛比分（BO1 使用地图比分），`result` 为 `胜` / `负`。
- `tags` 取值：`major`、`champion`、`mvp`、`milestone`、`notable`。

## 3. 注册（HTML 表单）

`POST /auth/register`
Content-Type: `application/x-www-form-urlencoded`

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `username` | string | 3–20 字符，字母/数字/下划线，唯一 |
| `password` | string | 8–72 字符 |
| `confirm` | string | 必须与 `password` 一致 |

- 成功：`303 See Other` → `next` 或 `/`，并设置会话 Cookie。
- 失败：`400`，重新渲染登录页并给出错误文案。
- 用户名冲突：`409`，文案「用户名已被占用」。

## 4. 登录（HTML 表单）

`POST /auth/login`

| 字段 | 类型 |
| --- | --- |
| `username` | string |
| `password` | string |
| `next` | string，可选，仅允许站内相对路径 |

- 成功：`303` → `next` 或 `/`。
- 失败：`400`，文案「用户名或密码错误」，不泄露账号是否存在。

## 5. 退出

`POST /auth/logout` → `303` → `/`

## 6. 当前用户（HTML）

`GET /me`
- 已登录：200，渲染个人页。
- 未登录：`303` → `/login?next=/me`。

## 7. 当前用户（JSON）

`GET /api/me`
- 已登录：

```json
{ "id": 1, "username": "player", "created_at": "2026-11-18T10:00:00+08:00" }
```

- 未登录：`401 {"detail": "未登录"}`

## 8. 会话与错误约定

- Cookie 名：`cs_session`；`HttpOnly`、`SameSite=Lax`、14 天有效。
- 生产环境必须通过 `CS_LEGENDS_SECRET` 注入随机密钥；开发环境有默认值。
- 表单错误采用服务端渲染，不返回 JSON；JSON 接口错误统一为 `{"detail": "..."}`。
- v1 不提供 JSON 注册/登录接口，避免与表单流程重复。
