# 项目状态

更新：2026-11-25

## 本轮结论

- 2026-11-25 基础账号上线（**取代**上方 2026-11-21「v2 暂不做账号」的范围决策）：OAuth2 密码模式 + JWT。新增 `src/cs_player/security.py`（argon2id、HS256 access token、HttpOnly Cookie、CSRF）、`accounts.py`（注册/认证/刷新轮换与重放吊销/限流）、`auth.py`（`/login`、`/register`、`/account`、`POST /auth/login|register|token|refresh|logout`、`GET /api/me`）、`templates/_account.html` 与三个账号页、`docs/auth-schema.sql`（`app_user` / `refresh_token` / `login_attempt` 三表，`CREATE TABLE IF NOT EXISTS` 增量应用）；`app.py` 挂 router + 下发 CSRF Cookie，`base.html` / `index.html` 加账号入口，`style.css` 加账号样式。只做登录态，**不含**收藏/评论等业务，也不含邮箱验证与找回密码。
- 2026-11-25 自检：`scripts/check_auth.py` 22 项全过（注册、重复注册 409、弱密码 422、argon2 哈希前缀、表单登录 + Cookie、`/api/me`、Bearer、`/auth/token`、refresh 轮换、旧 refresh 重放被拒并吊销整链、`/auth/logout`、未登录 `/account` 302、CSRF 403、5 次失败 429）；`scripts/check_parity.py` 仍 PARITY OK；8051 冒烟 `/` `/login` `/register` 200、`/account` 303、`/api/health` 200 `source=db`、`/api/me` 401、`/api/players/zywoo` 200。
- 2026-11-25 顺手修复既有 bug：`src/cs_player/repository.py` 用 `session.exec()` 取 `AppearanceMatch` 在 SQLAlchemy 2.1 下返回 Row，导致 DB 模式首页 `KeyError: 'appearance_id'`（500）——改为 `session.scalars()`。
- 2026-11-21 数据源切为 **MySQL 为准**：新增 `src/cs_player/config.py`（`.env` 自动加载 + `CS_LEGENDS_DB_URL` / `CS_LEGENDS_DATA_SOURCE`）、`.env.example`；默认读 MySQL，连接失败或未配置时回退内置 JSON 并打 warning（30 秒后自动重试库），`/api/health` 增加 `source` 字段暴露实际来源。实测两种模式 `/api/players/zywoo` 的 SHA256 相同、`/` 的 HTML 除端口外一致，DB 模式端到端 ~55ms（API）/ ~70ms（页面），与 JSON 模式同量级。
- 2026-11-21 文档事实校正：当前口径文档（`README.md`、`docs/PRD.md`、`docs/api-contract.md`、`docs/design-spec.md`、`docs/ROADMAP-v2.md`）中的旧口径「27 条生涯节点 / 25 条赛事 / 139 场」统一改为实际值——**84 条记录（82 条赛事 + 2 条里程碑）、398 场逐场赛果**，赛果截至 2026-11-15，带坐标赛事覆盖 **22 个国家/地区**；国界要素数由 177 改为 **178**（补充新加坡与马耳他轮廓）；移除 README/PRD 中已删除的 SQLite 与签名 Cookie 会话描述。本文件下方的任务卡目标与逐轮自测记录属历史记录，保留当时数字。
- 2026-11-21 范围决策：**v2 暂不做账号体系**（注册 / 登录 / 退出 / 收藏 / CSRF）。`docs/ROADMAP-v2.md` 中相关页面、接口、P0 项、阶段 5、CSRF 与账号测试条目全部标记为「暂不做」，阶段计划总工时相应下调。
- 2026-11-21 数据层可选 MySQL（SQLModel）：新增 `docs/db-schema.sql`（10 张表 + `v_appearance` 视图）、`scripts/gen_seed.py`（JSON → `scripts/seed.sql`）、`src/cs_player/models.py`（SQLModel 表模型）、`src/cs_player/repository.py`（SQLModel 查询层）；`src/cs_player/content.py` 改为按环境变量 `CS_LEGENDS_DB_URL` 分派 **JSON 或 MySQL** 双源，未设置时行为与之前完全相同。已灌库并校验：两种模式的 `/api/players/zywoo` 响应逐字节一致、`/` 渲染一致（`scripts/check_parity.py` 输出 PARITY OK）。
- 首页已从「Hero + 地图 + 时间线 + 荣誉墙」改为**全屏三维地球**（Globe.gl）。
- 左上角新增选手选择器（当前仅 ZywOo），为后续选手预留入口。
- 25 条赛事数据补齐 `organizer` 与 `matches`，共 139 场逐场赛果。
- 地球改为**按国家分块**：`static/data/countries.geojson`（177 个国家/地区，台湾地区并入中华人民共和国）渲染为独立多边形；鼠标悬停国家即高亮并抬升至 0.018，移出恢复。赛事光点 / 光环 / 年份标签已全部移除。
- 悬停国家时，右侧（移动端底部抽屉）直接展示该国全部赛事：国家名、`N 届赛事 · M 场比赛`、每届赛事的主办方、场馆、成绩、简介与逐场赛果；无赛事国家显示空状态文案。
- 举办过赛事的国家默认底色略亮；每个举办国显示该国**全部主办方**的小图标（德国 ESL+SL、瑞典 ESL+PGL，深色胶囊 + 主办方配色 + 届数角标），标记不拦截鼠标，悬停仍命中国家。
- 单击国家后面板**固定**：鼠标移出或悬停其他国家都不会关闭/顶掉面板，可从容阅读同国多届赛事；点海洋、`×` 或 Esc 取消固定。
- 地球背面与屏幕空间过近的标记自动隐藏，欧洲密集区不再叠字；滚轮放大后标记逐一分开展示。
- 地球默认缓慢自转，可拖拽旋转、滚轮/双指缩放；悬停国家时暂停自转，离开后 4 秒恢复。
- 契约文档已同步：`docs/PRD.md`、`docs/api-contract.md`、`docs/design-spec.md`。
- 2026-11-19 地球视觉打磨：国家面改为半透明（`0.72` / 举办国 `0.9`），透出 `earth-night.jpg` 城市灯光；悬停面降至 `0.34` 并配亮色描边；大气层改青色 `#5eead4`；球体加高光材质与左后下方轮廓光；页面加星空调点阵 + 三层色雾 + 径向暗角；主办方徽标加同色辉光与 4px 锚点；海拔过渡 260ms、曲率细分 3°；画布首帧 800ms 淡入；悬停有赛事国家时光标变 `pointer`。
- 2026-11-19 UI 降噪（unslop）：删除登录页的模拟雷达、扫描线、准星、假 HUD（`TACTICAL ARCHIVE` / `DE_DUST2 · 1:55`）与彩色光团，改为星点 + 一条行星球体地平线弧线；登录表单收进 400px 半透明面板。全站统一圆角（面板 16 / 卡片 14 / 控件 10），去掉 999px 胶囊按钮、`translateY` 位移动效、彩色外发光与 700/800 粗体；`@用户名` 改为进入 `/me` 的链接；个人页去掉 ACCOUNT 眉题、状态胶囊与 PBKDF2 实现细节，删除指向已移除锚点的「继续看时间线」死链。（该阶段页面已在本轮移除）
- 2026-11-19 移除登录功能：删除 `/login`、`/auth/login`、`/auth/register`、`/auth/logout`、`/me`、`/api/me` 路由，删除 `auth.py`、`db.py`、`login.html`、`me.html` 与 SessionMiddleware；地图页右上角账号入口、登录/退出按钮、`@用户名` 链接全部移除。站点改为纯只读展示，`/login`、`/me`、`/api/me` 返回 404。
- 2026-11-19 依赖精简：`pyproject.toml` 移除 `python-multipart`（表单解析）与 `itsdangerous`（会话签名），`uv lock` 后直接依赖仅保留 `fastapi`、`uvicorn`、`jinja2`；2026-11-21 因 MySQL 主数据源新增 `sqlmodel`、`pymysql`。
- 2026-11-19 赛事数据补全：按 HLTV 统计页 `matchType=BigEvents` 口径（79 届 Big Events）把 ZywOo 出道以来参加过的全部 Big Event 补进 `data/zywoo.json`，新增 57 届、259 场逐场赛果，合并后共 84 条记录（82 条赛事 + 2 条里程碑）、398 场逐场赛果。原 22 届 Big Event 与 3 条非 Big Event 历史条目（cs_summit 4、IEM Beijing-Haidian 2020 Europe、BLAST Premier Fall 2020 Finals）保留。
- 2026-11-19 数据口径说明：逐场赛果取自 HLTV 战队赛果页（`?team=9565&startDate/endDate`），只保留 Big Event 行并排除 RMR、Closed Qualifier、BLAST Bounty 线上阶段等非 Big Event 场次；Major 的 Challengers Stage 与 IEM Cologne 的 Play-in 归入同一届赛事。赛事城市/国家/场馆/主办方/起止日期取自 Liquipedia infobox（Malmö 2019、IEM Kraków 2026 为人工核对补录）。
- 2026-11-19 前端适配：新增赛事无逐场 `stage` 时列表自动切为三列（`match-list--plain`），不再出现空列；场馆缺失显示「未记录」而非误显示「线上赛」；城市名统一为中文。
- 2026-11-19 底图补点：Natural Earth 110m 底图缺新加坡，已补充新加坡多边形要素（178 个要素），使 BLAST Premier World Final 2024（圣淘沙）可在球面命中；国界版本号升至 `?v=20261120`。

## 任务卡

### T1 数据层：ZywOo 精选档案
- 目标：27 条赛事/里程碑数据，含坐标、名次、比分、来源。
- 期望产出：`src/cs_player/data/zywoo.json`。
- 验收标准：JSON 可解析；日期正序；有坐标事件的经纬度落在正确城市范围；每条有 `source`。
- 状态：已完成。

### T2 鉴权：注册 / 登录 / 退出 / 个人页
- 目标：本地账号体系，密码哈希，会话 Cookie。
- 验收标准：注册自动登录；重复用户名 409；错误密码 400；退出后 `/api/me` 401；密码不以明文落库。
- 状态：已回滚（2026-11-19 按要求移除登录功能，路由、模板、鉴权与数据库代码已删除）。

### T3 全屏地图页
- 目标：只保留世界地图与左上角选手选择器。
- 期望产出：`templates/index.html`、`static/css/style.css`、`static/js/map.js`。
- 验收标准：地图全屏可拖拽/缩放；23 个标记正常显示；同坐标标记错位；无时间线/筛选/Hero/荣誉墙。
- 状态：已完成。

### T4 赛事详情与逐场数据
- 目标：悬停或点按标记展示赛事详情与本届全部比赛。
- 期望产出：`data/zywoo.json` 的 `organizer`、`matches` 字段；`map.js` 详情面板。
- 验收标准：25 条赛事均有主办方；逐场列表含阶段、对手、比分、胜负；移动端底部抽屉可读。
- 状态：已完成。

### T5 验证与交付
- 目标：启动、地图、鉴权、API 自测。
- 验收标准：见 `docs/PRD.md` 第 6 节。
- 状态：已完成。

### T6 三维地球替换平面地图
- 目标：首页底图从 Leaflet 平面地图改为可旋转的 Globe.gl 三维地球。
- 期望产出：`templates/index.html`、`static/js/map.js`、`static/css/style.css`、`static/images/globe/`。
- 验收标准：地球可拖拽旋转、缩放；默认自转；23 个光点与脉冲环正常；悬停光点仍能打开含主办方与逐场赛果的详情；无 Leaflet 残留依赖。
- 状态：已完成。

### T7 国家分块地球与悬停信息
- 目标：地球按国家分块渲染；悬停国家高亮；去掉赛事光点，改为在右侧空白面板直接展示该国全部赛事。
- 期望产出：`static/data/countries.geojson`、`static/js/map.js`、`static/css/style.css`、`templates/index.html`。
- 验收标准：国家可命中悬停并高亮抬升；无光点/光环残留；有赛事国家展示全部赛事与逐场赛果；无赛事国家展示空状态；海洋区域关闭面板；Esc / `×` 关闭。
- 状态：已完成。

### T8 主办方标记
- 目标：让用户在世界视图就能看出哪些国家举办过比赛，并用主办方小图标区分赛事来源。
- 期望产出：`static/js/map.js` 标记层与去重逻辑、`static/css/style.css` 标记样式。
- 验收标准：每个举办国一枚标记并列出该国全部主办方；图标可读且带届数角标；不拦截国家悬停；背面与重叠标记隐藏；放大后逐一显示。
- 状态：已完成。

### T9 单击固定面板与全主办方徽标
- 目标：单击国家后面板不随鼠标移出关闭，便于阅读同国多届赛事；徽标列出该国全部主办方。
- 验收标准：单击国家 → 移出鼠标面板仍在且内容不变；悬停他国不顶掉固定面板；海洋 / `×` / Esc 取消固定；德国徽标为 ESL+SL、瑞典为 ESL+PGL。
- 状态：已完成。

### T10 三维地球视觉打磨
- 目标：解决国家面实色扁平、海岸线发黑阴影带、背景过空的问题，让地球更精致。
- 期望产出：`static/js/map.js`（配色、材质、灯光、相机、标记）、`static/css/style.css`（星空、暗角、徽标、光标、淡入）、`docs/design-spec.md` 第 4 节同步。
- 验收标准：陆地与海洋可区分；海岸线无粗黑边；悬停高亮柔和且不刺眼；徽标锚点指向坐标；无 console 报错；桌面与移动端视角都完整显示地球。
- 状态：已完成。

### T11 UI 降噪与视觉规范收敛
- 目标：按 unslop 审计结果收敛全局视觉，去掉模拟 HUD、彩色辉光、胶囊化控件与粗体堆叠，保留深空 + 地球的世界观。
- 期望产出：`templates/index.html`、`templates/login.html`、`templates/me.html`、`static/css/style.css`、`docs/design-spec.md`。
- 验收标准：登录页无雷达/扫描线/假数据 HUD；圆角与字重统一；桌面与移动端截图无溢出、无 console 报错。（登录页与个人页已在 T12 整体移除）
- 状态：已完成。

### T12 移除登录功能
- 目标：砍掉注册、登录、退出、个人页与账号入口，站点收敛为纯只读展示，先把前端打磨好。
- 期望产出：`app.py`、`templates/base.html`、`templates/index.html`、`static/css/style.css`、`docs/*`。
- 验收标准：`/`、`/api/health`、`/api/players/zywoo` 正常；`/login`、`/me`、`/api/me` 返回 404；页面无任何登录入口；`auth.py`、`db.py`、`login.html`、`me.html` 已删除且无残留引用。
- 状态：已完成。

### T13 补齐 HLTV Big Events 全部赛事
- 目标：把 ZywOo 出道（2019）以来参加过的、HLTV 认定为 Big Event 的赛事全部加入档案，并保留逐场赛果。
- 输入：HLTV 选手统计页 `?matchType=BigEvents`（79 届）、HLTV 战队赛果页（2019–2026 按年）、Liquipedia 赛事 infobox。
- 期望产出：`src/cs_player/data/zywoo.json`（84 条记录 / 398 场）、`static/data/countries.geojson`（+新加坡）、`static/js/map.js`、`static/css/style.css`、`docs/STATUS.md`。
- 验收标准：79 届 Big Event 全部有对应记录（标题或别名匹配）；每届有 `organizer`；每条赛事有 `matches`；日期正序；所有举办国能在国界数据中命中（线上赛除外）；`node --check map.js` 通过。
- 状态：已完成（服务端冒烟测试因本机 Shell 会话异常未能在本轮执行，见「风险 9」）。

## 自测记录

| 项 | 结果 | 备注 |
| --- | --- | --- |
| 依赖安装 | 通过 | 已有 `.venv` 为旧项目残留且被锁定，已用 pip 修复并安装依赖 |
| 服务启动 | 通过 | `.venv\Scripts\python.exe -m uvicorn cs_player.app:app --port 8000` |
| 首页 200 | 通过 | 仅含三维地球与选手选择器；无时间线/Hero/荣誉墙 |
| 地球渲染 | 通过 | 无头 Edge（SwiftShader）截图确认夜景地球、绿色大气层、177 个国家多边形，无光点残留 |
| 地球交互 | 通过 | CDP 真实鼠标事件网格扫描：命中加拿大/格陵兰/俄罗斯/德国/乌克兰/摩尔多瓦；俄罗斯面板「1 届赛事 · 4 场比赛」+ EPICENTER 2019 逐场赛果，德国「3 届赛事 · 15 场比赛」；无赛事国家显示空状态 |
| 国家数据 | 通过 | `countries.geojson` 177 个 feature、约 839KB（台湾地区为中华人民共和国要素内的独立环）；25 条赛事涉及的 15 个国家（法、德、瑞典、波兰、美、巴西、英、俄、马耳他、沙特、阿联酋、丹麦、葡萄牙、澳大利亚、匈牙利）全部命中 |
| 移动端 | 通过 | 390×844 设备模拟，地球铺满视口，选择器完整可见；点按国家弹出底部抽屉（390×122，无横向溢出），空状态文案正常 |
| 主办方标记 | 通过 | 15 个举办国生成标记；多主办方国家并列显示（德国 ESL2+SL、瑞典 ESL2+PGL）；背面与重叠标记按届数优先隐藏，滚轮放大后全部显示 |
| 标记不拦截悬停 | 通过 | 鼠标停在 ESL / BLAST 图标区域仍命中所在国家并打开面板；国家高亮与图标叠放正常 |
| 单击固定面板 | 通过 | CDP 实测：单击俄罗斯后鼠标移到海洋，面板保持「1 届赛事 · 4 场比赛」不关闭；Esc 后面板隐藏 |
| 赛事明细 | 通过 | 25 条赛事均有 `organizer`；逐场赛果共 139 场 |
| 静态资源 | 通过 | CSS/JS/纹理 200；`node --check map.js` 通过 |
| 地球视觉（T10） | 通过 | 无头 Edge 1440×900 截图：陆地/海洋层次清晰，无粗黑海岸带；星空与暗角自然；14 个标记带锚点 |
| 悬停高亮（T10） | 通过 | CDP 网格扫描命中俄罗斯并截图：绿色半透明高亮 + 亮描边，右侧面板「1 届赛事 · 4 场比赛」正常 |
| 标记可视性（T10） | 通过 | 首帧后 `#globe.is-ready`，canvas 1 个、标记 14 个；默认视角地球完整不裁边 |
| 地图页控件（T11） | 通过 | 1440×900 截图：选择器箭头为内联 SVG，提示缩短为一行；地球与 14 个标记正常 |
| 残留类名（T11） | 通过 | 全仓 Grep 无 `auth-radar|auth-crosshair|auth-glow|auth-hud|status-pill|auth-hero__bg|auth-hero__scrim` 引用 |
| 路由裁剪（T12） | 通过 | `/`、`/api/health`、`/api/players/zywoo` 均 200；`/login`、`/me`、`/api/me` 均 404；应用仅注册 4 条路由 |
| 前端无登录入口（T12） | 通过 | 无头 Edge 1440×900 截图：右上角无按钮，地球与 14 个标记正常；模板/JS 全仓无 `user`、`auth`、`login` 引用 |
| 代码清理（T12） | 通过 | `auth.py`、`db.py`、`login.html`、`me.html` 已删除；`app.py` 导入 `content` 后可正常启动 |
| 数据补全（T13） | 通过 | HLTV 79 届 Big Event 全部有对应记录（含别名 `PGL CS2 Major Copenhagen 2024`、`StarLadder Major Berlin 2019`）；新增 57 届 / 259 场 |
| 数据完整性（T13） | 通过 | 合并后 84 条记录 / 398 场；除 2 条里程碑外均有 `organizer` 与 `matches`；标题无重复；日期正序 |
| 国家命中（T13） | 通过 | 举办国全部在 178 要素国界数据中；仅线上赛「欧洲赛区」无坐标，不生成标记 |
| 前端适配（T13） | 通过 | `node --check map.js` 通过；无 `stage` 列表切三列；空场馆显示「未记录」；57 条赛事城市名中文化 |
| 服务冒烟（T13） | 通过 | `/`、`/api/health`、`/api/players/zywoo`、`countries.geojson`、`map.js` 均 200；接口返回 84 条记录 / 398 场 |
| 地球渲染（T13） | 通过 | 无头浏览器打开首页：`#globe.is-ready`、1 个 canvas、21 个主办国标记，含新增的中华人民共和国、新加坡、罗马尼亚、西班牙、荷兰、葡萄牙、土耳其、比利时 |

## 风险

1. **环境风险**：仓库内 `.venv` 原为其他项目残留（pyvenv.cfg 指向 `D:\projects\cs_player`），`uv sync` 因目录被占用无法重建。本轮改为 pip 修复该 venv。建议关闭占用进程后手动删除 `.venv` 并执行 `uv sync`，恢复标准 uv 流程。
2. **地球依赖网络与 WebGL**：Globe.gl 走 jsDelivr CDN，纹理已本地化；离线或浏览器不支持 WebGL 时无法渲染 3D 地球，仅显示提示。
3. **无服务端状态**：本期不提供账号与任何写接口，所有接口只读；后续重新引入账号时需补 CSRF、登录限流与密码哈希方案。
4. **国家数据体积**：`countries.geojson` 约 839KB，首次进入首页需一次静态请求；已本地化，不依赖 CDN，但弱网下会延后地球出现。若后续需要进一步压缩，可裁剪到赛事涉国 + 邻国的简化多边形。
5. **渲染开销**：178 个多边形常驻渲染，低端设备可能出现掉帧；已用 `polygonAltitude` 仅抬升悬停国家，避免逐帧动画。
6. **数据时效**：赛果截至 2026-11-15（BLAST Rivals 2026 Season 2），后续赛事需更新 JSON。
7. **数据口径**：BO1 使用地图比分，BO3/BO5 使用系列赛比分；逐场数据来自公开赛事页，若官方修订以官方为准。新增的 57 届赛事逐场记录没有 `stage` 字段（HLTV 赛果页不提供阶段），列表以三列呈现；原 22 届赛事的阶段信息保留。
8. **文档冲突（已解决）**：2026-11-18 确认三维地球为唯一基线方案，`docs/ROADMAP-v2.md` 已同步（技术栈、现状、非目标、技术方案、阶段 3、§7 实现细节、版权表、E2E 全部改为 Globe.gl；原「3D 地球列为非目标」与 Leaflet/瓦片表述已删除），并写入决策记录。
9. **验证缺口（T13）**：本轮工具 Shell 会话在后台启动 uvicorn 后无法再启动任何进程，服务端冒烟测试与页面截图未能执行；数据与前端改动均已通过 JSON 解析、覆盖率校验与 `node --check`。**2026-11-19 已补跑**：`/`、`/api/health`、`/api/players/zywoo`（84 条 / 398 场）、`countries.geojson`、`map.js` 均返回 200。
10. **日期口径**：赛事 `date` 取 Liquipedia 结束日期（`edate`），与 HLTV 最后一场比赛日期可能相差 1 天（时区/赛程表差异）；`date_label` 只精确到月，不影响展示。
11. **新加坡轮廓为近似值**：底图缺少新加坡，补充的多边形是按经纬度范围手绘的近似轮廓，仅用于球面命中与高亮，不代表精确国界。

## 阻塞

无。
