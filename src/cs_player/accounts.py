"""Account + token persistence: registration, login, refresh rotation, throttling.

Everything here talks to MySQL through :mod:`cs_player.repository`'s engine.  The
JWT/cookie mechanics live in :mod:`cs_player.security`; HTTP endpoints in
:mod:`cs_player.auth`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from fastapi import Request
from sqlmodel import Session, func, select

from . import config
from .models import LoginAttempt, RefreshToken, User
from .security import (
    burn_password_check,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    ttl_deadline,
    utcnow,
    verify_password,
)

log = logging.getLogger(__name__)

LOGIN_WINDOW_SECONDS = 15 * 60  # 限流窗口：15 分钟
LOGIN_MAX_FAILURES = 5  # 窗口内最多 5 次失败
PASSWORD_MIN_LENGTH = 8  # 密码最小长度
PASSWORD_MAX_LENGTH = 128  # 密码最大长度

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # 邮箱正则表达式
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5.-]{3,32}$")  # 用户名正则表达式


class AccountError(Exception):  # 账号操作错误基类
    """Base class for errors the HTTP layer turns into 4xx responses."""

    status_code = 400
    message = "账号操作失败"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message

class RegistrationError(AccountError):  # 注册错误
    status_code = 422
    message = "注册信息不合法"


class EmailTaken(AccountError):  # 邮箱已被注册错误
    status_code = 409
    message = "该邮箱已注册"


class UsernameTaken(AccountError):  # 用户名已被注册错误
    status_code = 409
    message = "该用户名已被使用"


class AuthError(AccountError):  # 认证错误
    status_code = 401
    message = "邮箱或密码不正确"


class RateLimited(AccountError):  # 限流错误
    status_code = 429
    message = "尝试次数过多，请 15 分钟后再试"


def normalise_email(email: str) -> str:  # 归一化邮箱
    return email.strip().lower()


def normalise_identifier(identifier: str) -> str:  # 归一化标识符
    return identifier.strip().lower()


def validate_password(password: str) -> None:  # 验证密码
    """Minimal policy: length + letter + digit (no email verification yet)."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise RegistrationError(f"密码至少 {PASSWORD_MIN_LENGTH} 位")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise RegistrationError(f"密码最多 {PASSWORD_MAX_LENGTH} 位")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise RegistrationError("密码需要同时包含字母和数字")


def validate_identity(email: str, username: str) -> None:  # 验证身份
    if not _EMAIL_RE.match(email):
        raise RegistrationError("邮箱格式不正确")
    if len(email) > 160:
        raise RegistrationError("邮箱过长")
    if not _USERNAME_RE.match(username):
        raise RegistrationError("用户名需 3–32 位，可含中文、字母、数字、下划线、点和短横线")


def get_by_login(db: Session, identifier: str) -> User | None:  # 根据登录标识符获取用户
    """Look up by email or username, case-insensitively."""
    key = normalise_identifier(identifier)
    statement = select(User).where(  # 构建查询语句
        (func.lower(User.email) == key) | (func.lower(User.username) == key)
    )
    return db.scalars(statement).first()     # 执行查询并返回结果


def create_user(     # 创建用户
    db: Session,
    *,  # 关键字参数
    email: str,
    username: str,
    password: str,
    display_name: str | None = None,
) -> User:
    """Validate, check uniqueness and insert a new account."""
    email = normalise_email(email)
    username = username.strip()
    validate_identity(email, username)
    validate_password(password)

    existing = db.scalars(  # 构建查询语句
        select(User).where(
            (func.lower(User.email) == email) | (func.lower(User.username) == username.lower())
        )
    ).first()     
    if existing is not None:    # 如果用户已存在
        if existing.email.lower() == email: # 如果邮箱已存在
            raise EmailTaken()
        raise UsernameTaken()

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip() or username,
        role="user",
        is_active=True,
        token_version=0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, identifier: str, password: str) -> User | None:
    """Verify credentials; unknown users still pay one hash check."""
    user = get_by_login(db, identifier)  # 根据登录标识符获取用户
    if user is None:  # 如果用户不存在
        burn_password_check(password)
        return None
    if not user.is_active:  # 如果用户未激活
        return None
    if not verify_password(password, user.password_hash):  # 如果密码错误
        return None
    return user


def issue_tokens(db: Session, user: User, request: Request) -> tuple[str, str]:
    """Mint an access token and persist a fresh refresh token."""
    access = create_access_token(user)  # 创建访问令牌
    raw_refresh = create_refresh_token()  # 创建刷新令牌
    db.add(
        RefreshToken(
            user_id=int(user.id),
            token_hash=hash_token(raw_refresh),
            issued_at=utcnow(),
            expires_at=ttl_deadline(config.refresh_ttl()),
            user_agent=(request.headers.get("user-agent") or "")[:200] or None,
            ip=(request.client.host if request.client else None),
        )
    )
    db.commit()
    return access, raw_refresh


def find_refresh(db: Session, raw_token: str) -> RefreshToken | None:
    return db.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    ).first()  # 执行查询并返回结果



def rotate_refresh(
    db: Session, raw_token: str, request: Request
) -> tuple[User, str, str]:
    """Consume a refresh token and return (user, new access, new refresh).

    Reuse of an already-rotated/revoked token is treated as theft: the whole
    chain is revoked and ``token_version`` is bumped so every access token dies.
    """
    row = find_refresh(db, raw_token)   # 根据原始刷新令牌获取记录
    if row is None:
        raise AuthError("刷新令牌无效")
    user = db.get(User, row.user_id)  # 根据用户 ID获取用户
    if user is None or not user.is_active:
        raise AuthError("账号不可用")

    if row.revoked_at is not None or row.replaced_by is not None:  # 如果刷新令牌已失效或已被替换
        log.warning("refresh token 重放：user=%s token=…%s", user.id, raw_token[-6:])  # 记录日志
        revoke_all(db, user)  # 失效所有访问令牌
        raise AuthError("刷新令牌已失效，请重新登录")

    if row.expires_at <= utcnow():  # 如果刷新令牌已过期
        row.revoked_at = utcnow()
        db.commit()
        raise AuthError("刷新令牌已过期")

    access, new_refresh = issue_tokens(db, user, request)  # 创建新的访问令牌和刷新令牌
    row.revoked_at = utcnow()  # 标记刷新令牌为失效
    row.replaced_by = hash_token(new_refresh)  # 记录新的刷新令牌
    db.commit()
    return user, access, new_refresh


def revoke_refresh(db: Session, raw_token: str) -> User | None:
    """Revoke a single refresh token (logout on this device)."""
    row = find_refresh(db, raw_token)   # 根据原始刷新令牌获取记录
    if row is None:
        return None
    row.revoked_at = row.revoked_at or utcnow()  # 标记刷新令牌为失效
    db.commit()
    return db.get(User, row.user_id)


def revoke_all(db: Session, user: User) -> None:
    """Log out every device and invalidate all outstanding access tokens."""
    now = utcnow()  # 获取当前时间
    for row in db.scalars(  # 构建查询语句
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all():
        row.revoked_at = now  # 标记刷新令牌为失效
    user.token_version = int(user.token_version) + 1  # 增加令牌令牌版本
    user.updated_at = now  # 更新用户更新时间
    db.add(user)
    db.commit()


def touch_login(db: Session, user: User) -> None:
    """Record a successful sign-in time."""
    user.last_login_at = utcnow()  # 更新用户最后登录时间
    user.updated_at = utcnow()
    db.add(user)
    db.commit()


def record_attempt(
    db: Session, identifier: str, ip: str, *, success: bool
) -> None:
    db.add(  # 添加登录尝试记录
        LoginAttempt(
            identifier=normalise_identifier(identifier)[:160],
            ip=(ip or "")[:45],
            success=success,
            created_at=utcnow(),
        )
    )
    db.commit()


def too_many_attempts(db: Session, identifier: str, ip: str) -> bool:
    """True when this identifier or IP has too many failures in the window."""
    since = utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)  # 计算时间窗口开始时间
    key = normalise_identifier(identifier)[:160]  # 归一化标识符
    failures = db.scalar(  # 执行查询并返回结果
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
            (LoginAttempt.identifier == key) | (LoginAttempt.ip == (ip or "")[:45]),
        )
    )
    return int(failures or 0) >= LOGIN_MAX_FAILURES  # 如果失败次数超过最大失败次数


def prune_attempts(db: Session) -> None:
    """Delete attempt rows older than the throttling window (maintenance)."""
    cutoff = utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS * 4)  # 计算截止时间
    for row in db.scalars(  # 构建查询语句
        select(LoginAttempt).where(LoginAttempt.created_at < cutoff)
    ).all():
        db.delete(row)
    db.commit()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"  # 获取客户端 IP 地址


def iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None  # 格式化时间戳
