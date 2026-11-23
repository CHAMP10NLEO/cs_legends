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
