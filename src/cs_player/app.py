"""FastAPI application for the CS Legends website."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import content

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="CS Legends")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    """让静态资源每次回源校验，避免浏览器长期缓存旧的国界数据。"""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    events = content.get_events()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "player": content.get_player(),
            "players": content.get_players(),
            "map_events": [event for event in events if event["has_coords"]],
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


def main() -> None:
    import uvicorn

    uvicorn.run("cs_player.app:app", host="127.0.0.1", port=8000, reload=False)
