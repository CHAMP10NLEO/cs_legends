"""Authentication routes: HTML pages (cookie flow) and API endpoints (bearer flow)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from . import accounts, config, security
from .security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    get_current_user,
    get_current_user_optional,
    set_auth_cookies,
    verify_csrf,
)

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def safe_next(value: str | None) -> str:    # 防止Open Redirect攻击
    """Sanitize a redirect target to ensure it points to the same site."""
    """Only allow same-site relative redirects (``/path``, never ``//host``)."""
    candidate = (value or "").strip()   # 移除首尾空格
    if candidate.startswith("/") and not candidate.startswith("//"):    # 确保是相对路径
        return candidate
    return "/"


def _db() -> Session:    # 获取数据库会话
    return security.session()


def _client_ip(request: Request) -> str:    # 获取客户端IP
    return accounts.client_ip(request)

# 渲染错误页面
def _render_error(
    request: Request,
    template: str,
    *,  #强调关键字传参数
    message: str,
    status_code: int = 400,
    context: dict | None = None,
) -> HTMLResponse:
    payload = {
        "request": request,
        "error": message,
        "user": get_current_user_optional(request),
        "next": safe_next(request.query_params.get("next")),
    }
    payload.update(context or {})
    return templates.TemplateResponse(request, template, payload, status_code=status_code)


@router.get("/login", response_class=HTMLResponse)  # 登录页面
def login_page(request: Request, registered: int = 0, next: str = "/"):
    """Login form; doubles as the ``/account`` redirect target."""
    if get_current_user_optional(request) is not None:  # 如果用户已登录
        return RedirectResponse(url=safe_next(next), status_code=status.HTTP_303_SEE_OTHER)  # 重定向到目标页面
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "user": None,
            "registered": bool(registered),
            "next": safe_next(next),
            "error": None,
        },
    )


@router.post("/auth/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str | None = Form(default=None),
    next: str = Form(default="/"),
):
    """Form login: sets HttpOnly cookies and redirects back into the site."""
    verify_csrf(request, csrf_token)    # 验证CSRF令牌
    ip = _client_ip(request)    # 获取客户端IP
    destination = safe_next(next)    # 获取安全的重定向目标

    def work() -> tuple[str, str, dict]:    # 工作函数
        with _db() as db:
            if accounts.too_many_attempts(db, username, ip):
                return "rate", "", {}
            user = accounts.authenticate(db, username, password)
            accounts.record_attempt(db, username, ip, success=user is not None)
            if user is None:
                return "bad", "", {}
            accounts.touch_login(db, user)
            access, refresh = accounts.issue_tokens(db, user, request)
            return "ok", access, {"access": access, "refresh": refresh, "user": user}

    outcome, _, data = await run_in_threadpool(work)    # 丢进线程池执行，异步运行工作函数

    if outcome == "rate":    # 如果次数超过限制
        return _render_error(
            request,
            "login.html",
            message=accounts.RateLimited.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            context={"next": destination, "registered": False},
        )
    if outcome == "bad":    # 如果登录失败
        return _render_error(
            request,
            "login.html",
            message="邮箱或密码不正确",
            status_code=status.HTTP_401_UNAUTHORIZED,
            context={"next": destination, "registered": False},
        )

    response = RedirectResponse(url=destination, status_code=status.HTTP_303_SEE_OTHER)    # 重定向到目标页面
    set_auth_cookies(response, data["access"], data["refresh"])    # 设置认证cookie
    return response


@router.get("/register", response_class=HTMLResponse)   # 注册页面
def register_page(request: Request, next: str = "/"):
    if get_current_user_optional(request) is not None:  # 如果用户已登录
        return RedirectResponse(url=safe_next(next), status_code=status.HTTP_303_SEE_OTHER)  # 重定向到目标页面
    return templates.TemplateResponse(   # 渲染注册页面
        request,
        "register.html",
        {"request": request, "user": None, "error": None, "next": safe_next(next), "form": {}},
    )


@router.post("/auth/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str | None = Form(default=None),
    next: str = Form(default="/"),
):
    """Create an account, then send the visitor to the login form."""
    verify_csrf(request, csrf_token)    # 验证CSRF令牌
    form_values = {"email": email, "username": username}
    destination = safe_next(next)    # 获取安全的重定向目标

    if password != password_confirm:    # 如果两次输入的密码不一致
        return _render_error(
            request,
            "register.html",
            message="两次输入的密码不一致",
            status_code=422,
            context={"form": form_values, "next": destination},
        )

    def work() -> str:    # 工作函数
        with _db() as db:
            try:
                accounts.create_user(
                    db, email=email, username=username, password=password
                )
            except accounts.AccountError as exc:
                return str(exc)
            return ""

    problem = await run_in_threadpool(work)    # 丢进线程池执行，异步运行工作函数
    if problem:    # 如果注册失败
        return _render_error(
            request,
            "register.html",
            message=problem,
            status_code=422,
            context={"form": form_values, "next": destination},
        )
    return RedirectResponse(
        url=f"/login?registered=1&next={destination}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/auth/token") 
async def token_endpoint(
    request: Request, form: OAuth2PasswordRequestForm = Depends()
) -> JSONResponse:
    """OAuth2 password grant: ``username`` may be an email or a username."""
    ip = _client_ip(request)     # 获取客户端IP地址

    def work() -> dict | None:    # 工作函数
        with _db() as db:
            if accounts.too_many_attempts(db, form.username, ip):    # 如果次数超过限制
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=accounts.RateLimited.message,
                )
            user = accounts.authenticate(db, form.username, form.password)  # 认证用户
            accounts.record_attempt(db, form.username, ip, success=user is not None)     # 记录登录尝试
            if user is None:    # 如果用户不存在
                return None
            accounts.touch_login(db, user)    # 更新用户最后登录时间
            access, refresh = accounts.issue_tokens(db, user, request)    # 发放令牌
            return {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "bearer",
                "expires_in": config.access_ttl(),
            }

    result = await run_in_threadpool(work)    # 丢进线程池执行，异步运行工作函数
    if result is None:    # 如果登录失败
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response = JSONResponse(result)    # 渲染JSON响应
    set_auth_cookies(response, result["access_token"], result["refresh_token"])    # 设置认证cookie
    return response


@router.post("/auth/refresh")
async def refresh_endpoint(request: Request) -> JSONResponse:
    """Rotate the refresh token; accepts a cookie or a JSON/form body token."""
    body_token: str | None = None    # 刷新令牌
    content_type = request.headers.get("content-type", "")    # 获取请求体类型
    if content_type.startswith("application/json"):    # 如果请求体是JSON格式
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            body_token = payload.get("refresh_token")
    elif content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):    # 如果请求体是表单数据格式
        form_data = await request.form()
        value = form_data.get("refresh_token")
        body_token = value if isinstance(value, str) else None

    raw = body_token or request.cookies.get(REFRESH_COOKIE)    # 获取刷新令牌
    if not raw:    # 如果刷新令牌不存在
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def work() -> dict:    # 工作函数
        with _db() as db:
            try:
                user, access, refresh = accounts.rotate_refresh(db, raw, request)    # 刷新令牌
            except accounts.AuthError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(exc),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "bearer",
                "expires_in": config.access_ttl(),
            }

    result = await run_in_threadpool(work)    # 丢进线程池执行，异步运行工作函数
    response = JSONResponse(result)    # 渲染JSON响应
    set_auth_cookies(response, result["access_token"], result["refresh_token"])    # 设置认证cookie
    return response


@router.post("/auth/logout")
async def logout(request: Request, csrf_token: str | None = Form(default=None)):
    """Revoke this device's refresh token, clear cookies and return home."""
    verify_csrf(request, csrf_token)    # 校验CSRF令牌
    raw = request.cookies.get(REFRESH_COOKIE)    # 获取刷新令牌

    def work() -> None:    # 工作函数
        with _db() as db:
            if raw:
                accounts.revoke_refresh(db, raw)

    await run_in_threadpool(work)    # 丢进线程池执行，异步运行工作函数
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)    # 渲染重定向响应
    clear_auth_cookies(response)    # 清除认证cookie
    return response


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    """Account page; guests are bounced to the login form."""
    user = get_current_user_optional(request)    # 获取当前用户
    if user is None:    # 如果用户不存在
        return RedirectResponse(
            url="/login?next=/account", status_code=status.HTTP_303_SEE_OTHER
        )
    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "request": request,
            "user": user,
            "created_at": accounts.iso(user.created_at),
            "last_login_at": accounts.iso(user.last_login_at),
        },
    )


@router.get("/api/me")
def me(user=Depends(get_current_user)) -> dict:
    """Current user as JSON (accepts Bearer or cookie)."""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": accounts.iso(user.created_at),
        "last_login_at": accounts.iso(user.last_login_at),
    }


__all__ = ["router", "templates", "ACCESS_COOKIE"]
