"""End-to-end check of the account flow against the real MySQL database.

Run from the project root:

    .venv\\Scripts\\python.exe scripts\\check_auth.py

It creates throwaway ``qa-*@example.com`` accounts, exercises register / login /
token / refresh rotation / reuse detection / logout / throttling, prints a
pass/fail line per step and removes its own rows at the end.

Requires ``CS_LEGENDS_DB_URL`` (loaded from ``.env``) and a JWT secret; a dev
fallback secret is used when ``CS_LEGENDS_JWT_SECRET`` is unset.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, delete, select  # noqa: E402

from cs_player import accounts, config  # noqa: E402
from cs_player.app import app  # noqa: E402
from cs_player.models import LoginAttempt, RefreshToken, User  # noqa: E402
from cs_player.repository import get_engine  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{PASS if condition else FAIL}] {label}{'' if condition else ' :: ' + detail}")
    if not condition:
        failures.append(label)


def cleanup(email_prefix: str = "qa-") -> None:
    with Session(get_engine()) as db:
        users = db.scalars(select(User).where(User.email.like(f"{email_prefix}%"))).all()
        for user in users:
            for row in db.scalars(
                select(RefreshToken).where(RefreshToken.user_id == user.id)
            ).all():
                db.delete(row)
            db.delete(user)
        for row in db.scalars(
            select(LoginAttempt).where(LoginAttempt.identifier.like(f"{email_prefix}%"))
        ).all():
            db.delete(row)
        db.commit()


def main() -> int:
    print(f"数据源：{config.db_url() or '内置 JSON（未配置 CS_LEGENDS_DB_URL）'}")
    if not config.db_url():
        print("跳过：本脚本只验证 MySQL 链路")
        return 2

    cleanup()
    client = TestClient(app, follow_redirects=False)

    email = "qa-main@example.com"
    username = "qa_main"
    password = "Sup3rSecret!"

    # ---- register -----------------------------------------------------------
    page = client.get("/register")
    csrf = page.cookies.get("csrf_token") or ""
    check("GET /register 返回 200", page.status_code == 200)
    check("注册页带 CSRF Cookie", bool(csrf))

    response = client.post(
        "/auth/register",
        data={
            "email": email,
            "username": username,
            "password": password,
            "password_confirm": password,
            "csrf_token": csrf,
        },
    )
    check(
        "POST /auth/register 302 → /login?registered=1",
        response.status_code == 303 and "registered=1" in response.headers.get("location", ""),
        f"{response.status_code} {response.headers.get('location')}",
    )

    # 重复注册 → 422（邮箱已占用）
    csrf = client.cookies.get("csrf_token") or csrf
    duplicate = client.post(
        "/auth/register",
        data={
            "email": email,
            "username": "qa_other",
            "password": password,
            "password_confirm": password,
            "csrf_token": csrf,
        },
    )
    check("重复邮箱注册被拒（422）", duplicate.status_code == 422, str(duplicate.status_code))

    # 弱密码 → 422
    weak = client.post(
        "/auth/register",
        data={
            "email": "qa-weak@example.com",
            "username": "qa_weak",
            "password": "short",
            "password_confirm": "short",
            "csrf_token": csrf,
        },
    )
    check("弱密码注册被拒（422）", weak.status_code == 422, str(weak.status_code))

    # 库中不应有明文密码
    with Session(get_engine()) as db:
        user = db.scalars(select(User).where(User.email == email)).first()
    stored = user.password_hash if user else ""
    check("密码以 argon2id 哈希存储", stored.startswith("$argon2") and password not in stored, stored[:24])

    # ---- login (form) -------------------------------------------------------
    csrf = client.cookies.get("csrf_token") or csrf
    login = client.post(
        "/auth/login",
        data={"username": email, "password": password, "csrf_token": csrf, "next": "/account"},
    )
    check("POST /auth/login 303 → /account", login.status_code == 303, str(login.status_code))
    check("登录后写入 access Cookie", bool(client.cookies.get("access_token")))
    check("登录后写入 refresh Cookie", bool(client.cookies.get("refresh_token")))

    me = client.get("/api/me")
    check("/api/me 200 且返回本人", me.status_code == 200 and me.json().get("email") == email, me.text[:120])

    home = client.get("/")
    check("首页渲染账号入口", home.status_code == 200 and username in home.text)

    # ---- API token endpoint -------------------------------------------------
    token = client.post("/auth/token", data={"username": username, "password": password})
    payload = token.json() if token.status_code == 200 else {}
    check(
        "POST /auth/token 返回 bearer 令牌",
        token.status_code == 200
        and payload.get("token_type") == "bearer"
        and payload.get("expires_in") == config.access_ttl()
        and bool(payload.get("access_token")),
        token.text[:160],
    )

    bearer = TestClient(app, follow_redirects=False)
    me_bearer = bearer.get(
        "/api/me", headers={"Authorization": f"Bearer {payload.get('access_token', '')}"}
    )
    check("Bearer 访问 /api/me 200", me_bearer.status_code == 200, me_bearer.text[:120])
    check("Bearer 访问 /account 200", bearer.get(
        "/account", headers={"Authorization": f"Bearer {payload.get('access_token', '')}"}
    ).status_code == 200)

    # ---- refresh rotation + reuse detection --------------------------------
    first_refresh = payload.get("refresh_token", "")
    rotated = client.post("/auth/refresh", json={"refresh_token": first_refresh})
    rotated_body = rotated.json() if rotated.status_code == 200 else {}
    check(
        "POST /auth/refresh 轮换出新令牌",
        rotated.status_code == 200 and rotated_body.get("refresh_token") not in (None, first_refresh),
        rotated.text[:160],
    )

    replay = client.post("/auth/refresh", json={"refresh_token": first_refresh})
    check("旧 refresh 重放被拒（401）", replay.status_code == 401, str(replay.status_code))

    after_replay = TestClient(app, follow_redirects=False)
    after_replay.cookies.set("access_token", rotated_body.get("access_token", ""))
    check(
        "重放后整链吊销：新 access 也失效（401）",
        after_replay.get("/api/me").status_code == 401,
    )

    # ---- logout -------------------------------------------------------------
    csrf = client.cookies.get("csrf_token") or csrf
    logout = client.post("/auth/logout", data={"csrf_token": csrf})
    check("POST /auth/logout 303 → /", logout.status_code == 303, str(logout.status_code))
    check("退出后 /api/me 401", client.get("/api/me").status_code == 401)

    # ---- guest redirects ----------------------------------------------------
    guest = TestClient(app, follow_redirects=False)
    account_redirect = guest.get("/account")
    check(
        "未登录 /account 302 → /login",
        account_redirect.status_code == 303
        and "/login" in account_redirect.headers.get("location", ""),
        str(account_redirect.status_code),
    )

    # ---- CSRF rejection -----------------------------------------------------
    csrf_missing = guest.post("/auth/login", data={"username": email, "password": password})
    check("缺少 CSRF 字段的表单被拒（403）", csrf_missing.status_code == 403, str(csrf_missing.status_code))

    # ---- throttling ---------------------------------------------------------
    throttle_client = TestClient(app, follow_redirects=False)
    throttle_email = "qa-throttle@example.com"
    codes = []
    for _ in range(6):
        throttle_client.get("/login")
        codes.append(
            throttle_client.post(
                "/auth/login",
                data={
                    "username": throttle_email,
                    "password": "wrong-password1",
                    "csrf_token": throttle_client.cookies.get("csrf_token") or "",
                },
            ).status_code
        )
    check(
        "同一账号 5 次失败后触发 429",
        429 in codes and codes.index(429) >= 5,
        f"statuses={codes}",
    )

    cleanup()
    print()
    if failures:
        print(f"失败 {len(failures)} 项：{', '.join(failures)}")
        return 1
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
