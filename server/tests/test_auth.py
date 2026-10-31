"""D-B：认证 API 集成测试（需 Postgres + seed 数据）。"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from scripts.seed import run_seed

client = TestClient(app)


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def test_login_success_and_me() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    assert login.status_code == 200
    body = login.json()
    assert body["code"] == 0
    token = body["data"]["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    me_data = me.json()["data"]
    assert me_data["user"]["username"] == settings.init_admin_username
    assert me_data["dept"]["name"]
    assert "超级管理员" in me_data["role_names"]
    codes = me_data["permission_codes"]
    assert "data:scope:all" in codes
    assert "system:update" in codes
    assert "dept:create" in codes
    assert "user:manage" not in codes



def test_login_failure() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    response = client.post(
        "/api/v1/auth/login",
        json={"username": settings.init_admin_username, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_me_without_token_returns_401() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_logout_with_token() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    token = login.json()["data"]["access_token"]
    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200
    assert logout.json()["code"] == 0
