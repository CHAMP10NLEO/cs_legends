"""Runtime configuration: where the data comes from.

MySQL is the primary, authoritative source. The connection string is read from
``CS_LEGENDS_DB_URL``; a local ``.env`` file in the project root (or the current
directory) is loaded first, so ``uv run`` works without exporting anything.

Set ``CS_LEGENDS_DATA_SOURCE=json`` to pin the bundled JSON file instead — handy
for offline demos, tests and comparisons.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # 项目根目录

DB_URL_ENV = "CS_LEGENDS_DB_URL"  # 数据库连接字符串环境变量名
SOURCE_ENV = "CS_LEGENDS_DATA_SOURCE"  # 数据来源环境变量名
JWT_SECRET_ENV = "CS_LEGENDS_JWT_SECRET"  # JWT 签名密钥环境变量名
ENVIRONMENT_ENV = "CS_LEGENDS_ENV"  # 运行环境（prod / dev）环境变量名
COOKIE_SECURE_ENV = "CS_LEGENDS_COOKIE_SECURE"  # 强制 Secure Cookie 的开关
COOKIE_DOMAIN_ENV = "CS_LEGENDS_COOKIE_DOMAIN"  # 认证 Cookie 的可选 Domain 属性

ACCESS_TTL_SECONDS = 15 * 60  # access token 有效期：15 分钟
REFRESH_TTL_SECONDS = 7 * 24 * 60 * 60  # refresh token 有效期：7 天
JWT_ALGORITHM = "HS256"  # JWT 签名算法

_DEV_SECRET = "dev-only-insecure-jwt-secret-change-me-0123456789"  # 仅开发环境使用
_dev_secret_warned = False  # 记录开发密钥警告是否已打印

_ENV_FILES = (PROJECT_ROOT / ".env", Path.cwd() / ".env")  # 候选文件路径
_env_loaded = False  # 记录是否已加载环境变量


def load_env_files() -> None:
    """Load ``.env`` files once, never overriding real environment variables."""
    global _env_loaded  # 全局变量
    if _env_loaded:  # 已加载，直接返回
        return
    _env_loaded = True  # 标记为已加载

    seen: set[Path] = set()  # 已加载的文件路径，用集合去重
    for candidate in _ENV_FILES:  # 遍历候选文件路径
        try:
            path = candidate.resolve()  # 把路径变成绝对路径,并解析掉符号链接和`..`
        except OSError:  # 读取路径失败，跳过
            continue
        if path in seen or not path.is_file():  # 已加载或不是文件，跳过
            continue
        seen.add(path)  # 标记为已加载
        try:
            lines = path.read_text(encoding="utf-8").splitlines()  # 读取文件内容并按行分割
        except OSError as exc:  # 读取文件失败，跳过
            print(f"[config] cannot read {path}: {exc}", file=sys.stderr)
            continue
        for raw in lines:   # 逐行处理
            line = raw.strip()  # 去掉首尾空格
            if not line or line.startswith("#") or "=" not in line:     # 空行或注释行或没有等号，跳过
                continue
            key, _, value = line.partition("=")  # 按等号分割键值对
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))  # 存储到环境变量，如果不存在则创建


def data_source() -> str:
    """``"db"`` (default) or ``"json"`` when explicitly pinned."""
    load_env_files()    # 加载环境变量
    return "json" if os.environ.get(SOURCE_ENV, "").strip().lower() == "json" else "db"  # 返回数据来源，如果不存在则返回 "db"


def db_url() -> str | None:
    """MySQL connection string, or ``None`` when the JSON source is pinned."""
    if data_source() == "json":  # 数据来源是 JSON，返回 None
        return None
    load_env_files()    # 加载环境变量
    return os.environ.get(DB_URL_ENV, "").strip() or None  # 返回数据库连接字符串，如果不存在则返回 None


def environment() -> str:
    """``"prod"`` or ``"dev"`` (default). Affects secret and cookie strictness."""
    load_env_files()    # 加载环境变量
    return os.environ.get(ENVIRONMENT_ENV, "").strip().lower() or "dev"  # 返回运行环境，如果不存在则返回 "dev"


def jwt_secret() -> str:
    """HS256 signing key: at least 32 bytes, never a default in production."""
    global _dev_secret_warned
    load_env_files()    # 加载环境变量
    secret = os.environ.get(JWT_SECRET_ENV, "").strip()  # 获取 JWT 签名密钥，去掉首尾空格，如果不存在则返回空字符串
    if secret:
        if len(secret) < 32 and environment() == "prod":
            raise RuntimeError(f"{JWT_SECRET_ENV} 至少需要 32 个字符")
        return secret
    if environment() == "prod":
        raise RuntimeError(
            f"生产环境必须设置 {JWT_SECRET_ENV}；"
            '可用 python -c "import secrets;print(secrets.token_urlsafe(48))" 生成'
        )
    if not _dev_secret_warned:
        _dev_secret_warned = True
        print(f"[config] 未设置 {JWT_SECRET_ENV}，使用开发用固定密钥（切勿用于生产）", file=sys.stderr)
    return _DEV_SECRET


def access_ttl() -> int:
    """Access-token lifetime in seconds."""
    return ACCESS_TTL_SECONDS


def refresh_ttl() -> int:
    """Refresh-token lifetime in seconds."""
    return REFRESH_TTL_SECONDS


def cookie_secure() -> bool:
    """``Secure`` cookies: on by default in production, overridable for local HTTPS."""
    load_env_files()    # 加载环境变量
    override = os.environ.get(COOKIE_SECURE_ENV, "").strip().lower()  # 获取 Cookie 是否安全
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    return environment() == "prod"


def cookie_domain() -> str | None:
    """Optional ``Domain`` attribute for the auth cookies."""
    load_env_files()
    return os.environ.get(COOKIE_DOMAIN_ENV, "").strip() or None
