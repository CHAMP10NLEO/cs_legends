"""Password hashing and signed-cookie session helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3

from fastapi import Request

from . import db

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def start_session(request: Request, user_id: int) -> None:
    request.session.clear()
    request.session["user_id"] = user_id


def end_session(request: Request) -> None:
    request.session.clear()


def current_user(request: Request) -> sqlite3.Row | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    user = db.get_user_by_id(user_id)
    if user is None:
        request.session.clear()
    return user


def safe_next(target: str | None, fallback: str = "/") -> str:
    if not target or not target.startswith("/") or target.startswith("//"):
        return fallback
    if "\\" in target or "\r" in target or "\n" in target:
        return fallback
    return target
