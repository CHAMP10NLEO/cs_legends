# CS Legends

用全屏三维地球回顾 CS 传奇选手的生涯轨迹：地球按国家分块，举办过赛事的国家会显示该国全部主办方的小图标（ESL / BLAST / PGL 等）；拖动旋转后把鼠标移到某个国家，该国家会高亮并弹出赛事面板，单击后面板固定不随鼠标消失，右侧直接列出在这个国家打过的全部赛事与逐场赛果。v1 聚焦 **ZywOo**，左上角选手选择器已为后续选手预留。

## 技术栈

- FastAPI + Jinja2 服务端渲染
- Globe.gl 2（Three.js）+ 国家级 GeoJSON 多边形
- 本地夜景地球纹理与 Natural Earth 国界数据
- 纯只读展示：**MySQL（SQLModel）为主数据源**，内置 JSON 作为兜底与初始种子
- 原生 CSS / JavaScript，无前端构建步骤

## 快速开始

首次运行需要先建库灌数据（MySQL 8）：

```powershell
# 1. 建库建表（会重建 cs_legends 库里的 10 张表与 1 个视图）
cmd /c "mysql -h 127.0.0.1 -u root -p --default-character-set=utf8mb4 < docs\db-schema.sql"

# 2. 从 JSON 生成 scripts/seed.sql
uv run python scripts/gen_seed.py

# 3. 灌数据
cmd /c "mysql -h 127.0.0.1 -u root -p --default-character-set=utf8mb4 cs_legends < scripts\seed.sql"

# 4. 配置连接串（复制模板后改密码；.env 已被 .gitignore 忽略）
Copy-Item .env.example .env
```

然后启动：

```powershell
uv sync
uv run uvicorn cs_player.app:app --reload --port 8000
```
或
```powershell
uv run cs-player
```

打开 http://127.0.0.1:8000

## 数据源：MySQL 为准，JSON 兜底

`src/cs_player/config.py` 决定读哪里，规则很直接：

1. 默认读 MySQL，连接串取 `CS_LEGENDS_DB_URL`；项目根目录的 `.env` 会先被加载，所以 `uv run` 不需要手动 export。
2. 连不上数据库、或根本没配置连接串时，**回退到内置 JSON** 并打一条 warning（30 秒后自动重试数据库），站点不会因此白屏。
3. 想固定用 JSON（离线演示、对比数据）就设 `CS_LEGENDS_DATA_SOURCE=json`。

> `.env` 里是明文密码，它已被 `.gitignore` 忽略、也不会出现在任何 HTTP 响应里（`/api/health` 只回 `source`）。但**不要把它贴进聊天、issue 或截图**；给别人演示请用只读账号，见下方「安全建议」。

当前数据源可以直接看健康检查：

```powershell
curl http://127.0.0.1:8000/api/health   # {"status":"ok","source":"db"}
```

两种数据源的 API 输出逐字节一致，可用 `uv run python scripts/check_parity.py` 校验。

注意 `scripts/gen_seed.py` 是**单向**的（JSON → SQL）：数据库是唯一可写的数据本体，改了库就直接生效；只有改了 JSON 才需要重新生成并灌一次 seed。

## 安全建议

连接串里带明文密码，所以：

- **别提交 `.env`**：`.gitignore` 已忽略 `.env` 与 `.env.*`（保留 `.env.example`）。校验命令：`git check-ignore -v .env`。
- **别用 root 跑应用**：建一个只读账号，只授 `SELECT`，`.env` 换成它即可。

```sql
CREATE USER 'cs_legends'@'localhost' IDENTIFIED BY '<强密码>';
GRANT SELECT ON cs_legends.* TO 'cs_legends'@'localhost';
```

- **收紧文件权限**（只留当前用户）：

```powershell
icacls .env /inheritance:r /grant:r "$env:USERNAME`:(F)"
```

- **让 MySQL 只监听本机**：`C:\ProgramData\MySQL\MySQL Server 8.0\my.ini` 的 `[mysqld]` 段加 `bind-address=127.0.0.1`，重启 `MySQL80` 服务；当前实测是 `*`（监听 0.0.0.0:3306）。
- 密码一旦出现在聊天、截图、日志或提交历史里，就当它已泄露，换掉再更新 `.env`。

## 页面与接口

| 路径 | 说明 |
| --- | --- |
| `/` | 全屏三维地球：选手选择器、国家分块与高亮、主办方图标、悬停国家查看赛事 |
| `/api/health` | 健康检查，返回当前数据源（`db` / `json`） |
| `/api/players/zywoo` | ZywOo 档案、统计与事件 JSON |

契约详见 [docs/api-contract.md](docs/api-contract.md)。

## 目录

```
docs/                     PRD、接口契约、设计规范、状态、建表 SQL
scripts/                  从 JSON 生成 seed.sql、双源一致性校验
.env.example              连接串模板（复制为 .env）
src/cs_player/
  app.py                  FastAPI 路由与页面
  config.py               数据源与连接串配置（.env / 环境变量）
  content.py              数据读取入口，整理赛事数据
  repository.py           SQLModel 版查询层，输出与 JSON 同形
  models.py               SQLModel 表模型（10 张表）
  data/zywoo.json         种子数据：84 条生涯节点（82 条赛事含逐场赛果）
  templates/              Jinja2 模板
  static/                 CSS / JS
  static/data/            Natural Earth 国界 GeoJSON
```

## 数据说明

赛果截至 2026-11-15，来源为 Liquipedia、HLTV、ESL / BLAST / StarLadder / PGL 官方赛事页。
82 条赛事均含主办方与逐场赛果（共 398 场），覆盖 22 个国家/地区；线上赛与生涯里程碑无坐标，保留在 API 中，但不出现在地球面板。举办国在球面显示主办方小图标，密集区域会按屏幕距离暂隐重叠图标，滚轮放大后全部显示。本站为非商业粉丝项目。

## 已知限制

- Globe.gl 走 jsDelivr CDN，需要外网；地球纹理与国界数据已本地化，断网时无法呈现 3D 地球。
- 需要浏览器支持 WebGL。
- 国界 GeoJSON 共 178 个国家/地区（台湾地区并入中华人民共和国）、约 839KB，首次加载需一次静态请求。
- 无账号、无写接口，因此没有 CSRF 防护需求；若后续恢复账号体系，需补 CSRF 与登录限流。
- 单选手、单进程内存缓存（JSON 文件的 `lru_cache`、MySQL 连接池），改数据后需重启服务，暂不支持多实例热更新。
- 数据以 MySQL 为准，JSON 只是种子与兜底：两者不一致时以库里的数据为准（`/api/health` 的 `source` 会显示实际来源）。
