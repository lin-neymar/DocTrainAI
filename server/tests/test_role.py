"""F3：角色 / 权限 API 集成测试（需 Postgres + seed）。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
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


def test_permissions_and_roles_require_auth() -> None:
    assert client.get("/api/v1/permissions").status_code == 401
    assert client.get("/api/v1/roles").status_code == 401


def test_list_permissions_from_db(admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/permissions", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert isinstance(items, list)
    codes = {p["code"] for p in items}
    assert "role:manage" in codes
    assert "data:scope:all" in codes
    assert len(codes) >= 9


def test_create_update_replace_permissions_and_delete(
    admin_headers: dict[str, str],
) -> None:
    code = f"custom_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={"code": code, "name": "自定义角色"},
    )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["code"] == code
    assert body["permission_codes"] == []
    role_id = body["id"]

    listed = client.get("/api/v1/roles?page=1&page_size=100", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] >= 1

    updated = client.put(
        f"/api/v1/roles/{role_id}",
        headers=admin_headers,
        json={"name": "自定义角色-改"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "自定义角色-改"

    replaced = client.put(
        f"/api/v1/roles/{role_id}/permissions",
        headers=admin_headers,
        json={"permission_codes": ["doc:read", "course:read"]},
    )
    assert replaced.status_code == 200
    assert set(replaced.json()["data"]["permission_codes"]) == {
        "doc:read",
        "course:read",
    }

    detail = client.get(f"/api/v1/roles/{role_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert set(detail.json()["data"]["permission_codes"]) == {
        "doc:read",
        "course:read",
    }

    unknown = client.put(
        f"/api/v1/roles/{role_id}/permissions",
        headers=admin_headers,
        json={"permission_codes": ["doc:read", "not:a:real:perm"]},
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == 40400

    deleted = client.delete(f"/api/v1/roles/{role_id}", headers=admin_headers)
    assert deleted.status_code == 200

    again = client.get(f"/api/v1/roles/{role_id}", headers=admin_headers)
    assert again.status_code == 404


def test_cannot_delete_role_with_active_users(
    admin_headers: dict[str, str],
) -> None:
    # 初始管理员一定绑定 super_admin → 软删应 409
    with SessionLocal() as session:
        super_admin = session.scalar(
            select(Role).where(
                Role.code == "super_admin", Role.is_deleted.is_(False)
            )
        )
        assert super_admin is not None
        role_id = str(super_admin.id)

    resp = client.delete(f"/api/v1/roles/{role_id}", headers=admin_headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == 40900


def test_duplicate_role_code_conflict(admin_headers: dict[str, str]) -> None:
    code = f"dup_{uuid.uuid4().hex[:8]}"
    payload = {"code": code, "name": "角色A"}
    assert (
        client.post("/api/v1/roles", headers=admin_headers, json=payload).status_code
        == 200
    )
    again = client.post("/api/v1/roles", headers=admin_headers, json=payload)
    assert again.status_code == 409
    assert again.json()["code"] == 40900
