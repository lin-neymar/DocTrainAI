"""F2：用户 API 集成测试（需 Postgres + seed）。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.system.dept import Dept
from app.models.system.role import Role
from scripts.seed import run_seed

client = TestClient(app)


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def _admin_headers() -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")
    return _admin_headers()


def _root_and_staff_role() -> tuple[str, str]:
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        staff = session.scalar(
            select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
        )
        assert root is not None and staff is not None
        return str(root.id), str(staff.id)


def test_users_require_auth() -> None:
    assert client.get("/api/v1/users").status_code == 401


def test_create_list_reset_password_and_delete(admin_headers: dict[str, str]) -> None:
    root_id, staff_role_id = _root_and_staff_role()
    username = f"u_f2_{uuid.uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": username,
            "password": "pass1234",
            "dept_id": root_id,
            "role_ids": [staff_role_id],
        },
    )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["username"] == username
    assert "password_hash" not in body
    assert staff_role_id in body["role_ids"]
    user_id = body["id"]

    listed = client.get("/api/v1/users?page=1&page_size=100", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

    reset = client.put(
        f"/api/v1/users/{user_id}/password",
        headers=admin_headers,
        json={"password": "newpass99"},
    )
    assert reset.status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "newpass99"},
    )
    assert login.status_code == 200

    deleted = client.delete(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert deleted.status_code == 200

    again = client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
    assert again.status_code == 404


def test_cannot_delete_self(admin_headers: dict[str, str]) -> None:
    me = client.get("/api/v1/auth/me", headers=admin_headers)
    my_id = me.json()["data"]["user"]["id"]
    resp = client.delete(f"/api/v1/users/{my_id}", headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == 40900


def test_duplicate_username_conflict(admin_headers: dict[str, str]) -> None:
    root_id, staff_role_id = _root_and_staff_role()
    username = f"dup_f2_{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "password": "pass1234",
        "dept_id": root_id,
        "role_ids": [staff_role_id],
    }
    assert client.post("/api/v1/users", headers=admin_headers, json=payload).status_code == 200
    again = client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert again.status_code == 409
    assert again.json()["code"] == 40900
