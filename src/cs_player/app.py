"""FastAPI application for the CS Legends website."""

from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, content, db

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="CS Legends", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("CS_LEGENDS_SECRET", "dev-only-change-me-cs-legends"),
    session_cookie="cs_session",
    max_age=14 * 24 * 60 * 60,
    same_site="lax",
    https_only=os.getenv("CS_LEGENDS_HTTPS_ONLY") == "1",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def human_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def render_login(
    request: Request,
    *,
    mode: str = "login",
    error: str | None = None,
    username: str = "",
    next_url: str = "/",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "user": None,
            "mode": mode,
            "error": error,
            "username": username,
            "next_url": auth.safe_next(next_url),
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    user = auth.current_user(request)
    events = content.get_events()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "user": dict(user) if user else None,
            "player": content.get_player(),
            "players": content.get_players(),
            "map_events": [event for event in events if event["has_coords"]],
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return render_login(request, next_url=next)


@app.post("/auth/login")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    username = username.strip()
    user = db.get_user_by_username(username)
    if user is None or not auth.verify_password(password, user["password_hash"]):
        return render_login(
            request,
            error="用户名或密码错误",
            username=username,
            next_url=next,
            status_code=400,
        )
    auth.start_session(request, int(user["id"]))
    return RedirectResponse(auth.safe_next(next), status_code=303)


@app.post("/auth/register")
def register(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
    next: str = Form("/"),
):
    username = username.strip()
    if not USERNAME_RE.match(username):
        return render_login(
            request,
            mode="register",
            error="用户名需为 3–20 位字母、数字或下划线",
            username=username,
            next_url=next,
            status_code=400,
        )
    if not 8 <= len(password) <= 72:
        return render_login(
            request,
            mode="register",
            error="密码长度需为 8–72 位",
            username=username,
            next_url=next,
            status_code=400,
        )
    if password != confirm:
        return render_login(
            request,
            mode="register",
            error="两次输入的密码不一致",
            username=username,
            next_url=next,
            status_code=400,
        )
    user_id = db.create_user(username, auth.hash_password(password))
    if user_id is None:
        return render_login(
            request,
            mode="register",
            error="用户名已被占用",
            username=username,
            next_url=next,
            status_code=409,
        )
    auth.start_session(request, user_id)
    return RedirectResponse(auth.safe_next(next), status_code=303)


@app.post("/auth/logout")
def logout(request: Request):
    auth.end_session(request)
    return RedirectResponse("/", status_code=303)


@app.get("/me", response_class=HTMLResponse)
def me(request: Request):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login?next=/me", status_code=303)
    return templates.TemplateResponse(
        request,
        "me.html",
        {
            "request": request,
            "user": dict(user),
            "created_at": human_time(user["created_at"]),
            "player": content.get_player(),
            "event_count": len(content.get_events()),
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/players/zywoo")
def player_api() -> JSONResponse:
    return JSONResponse(
        {
            "player": content.get_player(),
            "stats": content.get_stats(),
            "events": content.public_events(content.get_events()),
        }
    )


@app.get("/api/me")
def me_api(request: Request):
    user = auth.current_user(request)
    if user is None:
        return JSONResponse({"detail": "未登录"}, status_code=401)
    return {
        "id": user["id"],
        "username": user["username"],
        "created_at": user["created_at"],
    }


def main() -> None:
    import uvicorn

    uvicorn.run("cs_player.app:app", host="127.0.0.1", port=8000, reload=False)
