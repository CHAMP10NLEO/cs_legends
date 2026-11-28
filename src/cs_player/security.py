"""Password hashing, JWT issuance/verification, auth dependencies and cookies.

Two entry points share the same access token:

* browsers: ``POST /auth/login`` sets an HttpOnly cookie and redirects;
* API clients: ``POST /auth/token`` returns ``{"access_token": ...}`` for the
  ``Authorization: Bearer`` header.

``get_current_user`` therefore checks the header first and the cookie second.
Access tokens live 15 minutes; the opaque refresh token (7 days, rotated on every
use) is what keeps a browser logged in.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from pwdlib import PasswordHash
from sqlmodel import Session

from . import config
from .models import User
from .repository import get_engine

ACCESS_COOKIE = "access_token"  # 浏览器用的 access token Cookie 名
REFRESH_COOKIE = "refresh_token"  # refresh token Cookie 名
CSRF_COOKIE = "csrf_token"  # 双提交 CSRF 校验 Cookie 名
REFRESH_COOKIE_PATH = "/auth"  # refresh / logout 都在 /auth 下

_pwd = PasswordHash.recommended()  # argon2id
_DUMMY_HASH: str | None = None  # 未知用户时也做一次校验，避免计时枚举


class TokenError(Exception):
    """Raised when an access token is missing, malformed, expired or stale."""


def hash_password(password: str) -> str:    
    """Hash a plaintext password with argon2id."""
    return _pwd.hash(password)  # 对密码进行哈希处理


def verify_password(password: str, password_hash: str) -> bool:  # 校验密码
    """Constant-ish time verification; never raises on a malformed hash."""
    try:
        return _pwd.verify(password, password_hash)
    except Exception:  # noqa: BLE001 - 损坏的哈希等同于校验失败
        return False


def _dummy_hash() -> str:  # 生成一个临时密码哈希，用于计时枚举
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password-for-timing")
    return _DUMMY_HASH


def burn_password_check(password: str) -> None:  # 对密码进行哈希校验，用于计时枚举
    """Run a hash verification against a throwaway hash (timing equalisation)."""
    verify_password(password, _dummy_hash())


def session() -> Session:  # 打开一个 SQLModel 会话
    """Open a SQLModel session against the configured MySQL engine."""
    return Session(get_engine())


def _now() -> datetime:  # 获取当前UTC时间
    return datetime.now(timezone.utc)


def create_access_token(user: User) -> str:
    """Signed HS256 access token carrying sub / jti / iat / exp / ver."""
    now = _now()
    payload = {
        "sub": str(user.id),     # subject 用户ID
        "jti": uuid.uuid4().hex,    # jwt id 该token的唯一标识
        "iat": int(now.timestamp()),  # issued at 发布时间
        "exp": int((now + timedelta(seconds=config.access_ttl())).timestamp()),  # expires at 过期时间
        "ver": user.token_version,  # version 版本号
        "typ": "access",  # token type 访问token
    }
    return jwt.encode(payload, config.jwt_secret(), algorithm=config.JWT_ALGORITHM)


def create_refresh_token() -> str:
    """Opaque 256-bit refresh token; only its sha256 is stored server-side."""
    return secrets.token_urlsafe(32)     # 生成一个安全的随机token


def hash_token(token: str) -> str:
    """sha256 hex digest of a refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()     # 对token进行哈希处理


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token, raising :class:`TokenError`."""
    try:     # 解码token
        payload = jwt.decode(
            token, config.jwt_secret(), algorithms=[config.JWT_ALGORITHM]
        )
    except jwt.PyJWTError as exc:  # 解码token失败
        raise TokenError(str(exc)) from exc
    if payload.get("typ") != "access":  # 校验token类型
        raise TokenError("wrong token type")
    if not payload.get("sub"):  # 校验用户id
        raise TokenError("missing subject")
    return payload


def load_user_from_token(token: str, db: Session) -> User:  # 从token加载用户
    """Resolve a token to an active :class:`User` (checks ``token_version``)."""
    payload = decode_access_token(token)  # 解码token
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise TokenError("unknown or disabled user")
    if int(payload.get("ver", -1)) != user.token_version:
        raise TokenError("token revoked")   
    return user


def _bearer_token(request: Request) -> str | None:  # 从请求头中获取Bearer token
    header = request.headers.get("Authorization", "")  # 获取Authorization头
    scheme, _, value = header.partition(" ")  # 解析Authorization头
    if scheme.lower() == "bearer" and value.strip():  # 校验Bearer token
        return value.strip()
    return None


def _unauthorized(detail: str = "登录状态无效或已过期") -> HTTPException:  # 生成未授权异常
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request, db: Session = Depends(session)) -> User:
    """Required auth: ``Authorization: Bearer`` first, then the access cookie."""
    token = _bearer_token(request) or request.cookies.get(ACCESS_COOKIE)     # 从请求头或cookie中获取token
    if not token:
        raise _unauthorized("未登录")
    try:
        return load_user_from_token(token, db)
    except TokenError as exc:
        raise _unauthorized() from exc


def get_current_user_optional(request: Request) -> User | None:
    """Never raises: returns ``None`` for guests, used by SSR pages."""
    token = _bearer_token(request) or request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        with session() as db:
            return load_user_from_token(token, db)
    except Exception:  # noqa: BLE001 - 首页不能因为令牌失效而 500
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency for future admin-only routes."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:     # 设置认证cookie
    """Attach the HttpOnly access + refresh cookies to a response."""
    common = {
        "httponly": True,
        "secure": config.cookie_secure(),
        "samesite": "lax",
        "domain": config.cookie_domain(),
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=config.access_ttl(),
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=config.refresh_ttl(),
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:     # 清除认证cookie
    """Expire both auth cookies."""
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=config.cookie_domain())
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, domain=config.cookie_domain()
    )


def new_csrf_token() -> str:     # 生成CSRF token
    """Random double-submit CSRF token."""
    return secrets.token_urlsafe(32)


def ensure_csrf(request: Request, response: Response) -> str:     # 确保CSRF token存在
    """Return the CSRF token for this request, setting the cookie when missing."""
    token = request.cookies.get(CSRF_COOKIE) or ""
    if not token:
        token = new_csrf_token()
        response.set_cookie(
            CSRF_COOKIE,
            token,
            httponly=False,
            secure=config.cookie_secure(),
            samesite="lax",
            domain=config.cookie_domain(),
            path="/",
        )
    request.state.csrf_token = token
    return token


def verify_csrf(request: Request, submitted: str | None) -> None:     # 校验CSRF token
    """Reject a form POST whose CSRF field does not match the cookie."""
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not cookie or not submitted or not hmac.compare_digest(cookie, submitted):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")


def random_state() -> str:     # 生成随机状态
    """Random suffix used in log lines instead of token material."""
    return secrets.token_hex(4)


def seconds_until(expires_at: datetime) -> int:     # 计算剩余生命周期
    """Remaining lifetime in whole seconds, never negative."""
    delta = expires_at.replace(tzinfo=timezone.utc) - _now()
    return max(0, int(delta.total_seconds()))


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ttl_deadline(seconds: int) -> datetime:
    """Naive UTC timestamp ``seconds`` in the future."""
    return utcnow() + timedelta(seconds=seconds)


def monotonic() -> float:
    """Monotonic clock helper for tests."""
    return time.monotonic()
