"""FastAPI application for the CS Legends website."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, content, security
from .security import CSRF_COOKIE, get_current_user_optional, new_csrf_token

BASE_DIR = Path(__file__).resolve().parent  # 项目父目录，即`src/cs_player`
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))  # 模板目录

app = FastAPI(title="CS Legends")  # 创建FastAPI实例
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")  # 挂载静态文件目录，如CSS、JS、图片等
app.include_router(auth.router)  # 登录 / 注册 / 账号接口


@app.middleware("http")  # 中间件
async def revalidate_static(request: Request, call_next):
    """让静态资源每次回源校验，避免浏览器长期缓存旧的国界数据。"""
    response = await call_next(request)  # 调用下一个中间件或路由处理函数，获取响应
    # 如果请求路径以`/static/`开头，设置响应头为`no-cache`，避免浏览器缓存旧的静态资源
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")  # 中间件
async def csrf_cookie(request: Request, call_next):
    """给每个访客发一枚双提交 CSRF token，模板里直接用 request.state.csrf_token。"""
    fresh = CSRF_COOKIE not in request.cookies  # 如果请求中没有CSRF cookie，认为是新的访客
    token = request.cookies.get(CSRF_COOKIE) or new_csrf_token()  # 如果有CSRF cookie，使用它；否则生成新的CSRF token
    request.state.csrf_token = token    # 将CSRF token存储在请求状态中，方便模板使用
    response = await call_next(request)
    if fresh:    # 如果是新的访客，设置CSRF cookie
        response.set_cookie(
            CSRF_COOKIE,
            token,
            httponly=False,
            secure=security.config.cookie_secure(),
            samesite="lax",
            path="/",
        )
    return response


@app.get("/", response_class=HTMLResponse)  # 首页路由
def home(request: Request):
    events = content.get_events()   # 获取所有事件
    return templates.TemplateResponse(  # 渲染HTML模板
        request,
        "index.html",
        {
            "request": request,
            "player": content.get_player(),
            "players": content.get_players(),
            "map_events": [event for event in events if event["has_coords"]],
            "user": get_current_user_optional(request),
        },
    )


@app.get("/api/health")  # 健康检查路由
def health() -> dict[str, str]:   # 返回健康状态
    return {"status": "ok", "source": content.current_source()}


@app.get("/api/players/zywoo")  # 选手API路由
def player_api() -> JSONResponse:   # 获取选手信息
    return JSONResponse(
        {
            "player": content.get_player(),
            "stats": content.get_stats(),
            "events": content.public_events(content.get_events()),
        }
    )


def main() -> None:   # 主函数，用于启动FastAPI应用
    import uvicorn

    uvicorn.run("cs_player.app:app", host="127.0.0.1", port=8000, reload=False)
