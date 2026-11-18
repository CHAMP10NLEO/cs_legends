# CS Legends

用全屏三维地球回顾 CS 传奇选手的生涯轨迹：地球按国家分块，举办过赛事的国家会显示该国全部主办方的小图标（ESL / BLAST / PGL 等）；拖动旋转后把鼠标移到某个国家，该国家会高亮并弹出赛事面板，单击后面板固定不随鼠标消失，右侧直接列出在这个国家打过的全部赛事与逐场赛果。v1 聚焦 **ZywOo**，左上角选手选择器已为后续选手预留。

## 技术栈

- FastAPI + Jinja2 服务端渲染
- Globe.gl 2（Three.js）+ 国家级 GeoJSON 多边形
- 本地夜景地球纹理与 Natural Earth 国界数据
- SQLite + 签名 Cookie 会话（PBKDF2 密码哈希）
- 原生 CSS / JavaScript，无前端构建步骤

## 快速开始

```powershell
uv sync
uv run uvicorn cs_player.app:app --reload --port 8000
```

打开 http://127.0.0.1:8000

生产环境请设置随机会话密钥：

```powershell
$env:CS_LEGENDS_SECRET = "替换为足够长的随机字符串"
$env:CS_LEGENDS_HTTPS_ONLY = "1"
```

可选环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CS_LEGENDS_SECRET` | 开发用默认值 | 会话签名密钥 |
| `CS_LEGENDS_DB` | `./data/cs_legends.db` | SQLite 路径 |
| `CS_LEGENDS_HTTPS_ONLY` | 未设置 | 设为 `1` 时 Cookie 仅 HTTPS |

## 页面与接口

| 路径 | 说明 |
| --- | --- |
| `/` | 全屏三维地球：选手选择器、国家分块与高亮、主办方图标、悬停国家查看赛事 |
| `/login` | 登录 / 注册（成功后回到地图） |
| `/me` | 个人页（需登录） |
| `/api/health` | 健康检查 |
| `/api/players/zywoo` | ZywOo 档案、统计与事件 JSON |
| `/api/me` | 当前用户 JSON（需登录） |

契约详见 [docs/api-contract.md](docs/api-contract.md)。

## 目录

```
docs/                     PRD、接口契约、设计规范、状态
src/cs_player/
  app.py                  FastAPI 路由与页面
  auth.py                 密码哈希、会话
  db.py                   SQLite
  content.py              读取与整理赛事数据、选手列表
  data/zywoo.json         选手与 27 条生涯节点（25 条赛事含逐场赛果）
  templates/              Jinja2 模板
  static/                 CSS / JS
  static/data/            Natural Earth 国界 GeoJSON
```

## 数据说明

赛果截至 2026-10-11，来源为 Liquipedia、HLTV、ESL / BLAST / StarLadder / PGL 官方赛事页。
25 条赛事均含主办方与逐场赛果（共 139 场）；线上赛（`欧洲赛区`）保留在 API 中，但不归属任何国家，不出现在地球面板。举办国在球面显示主办方小图标，密集区域会按屏幕距离暂隐重叠图标，滚轮放大后全部显示。本站为非商业粉丝项目。

## 已知限制

- Globe.gl 走 jsDelivr CDN，需要外网；地球纹理与国界数据已本地化，断网时无法呈现 3D 地球。
- 需要浏览器支持 WebGL。
- 国界 GeoJSON 共 178 个国家/地区、约 820KB，首次加载需一次静态请求。
- v1 仅依赖 `SameSite=Lax`，公网部署前应补 CSRF token。
- 单选手、单机 SQLite，暂不支持多实例部署。
