"""F1：部门 API 集成测试（需 Postgres + seed）。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.system.dept import Dept
from scripts.seed import run_seed

client = TestClient(app)


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def _admin_token() -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")
    return _auth(_admin_token())


def test_list_and_tree_require_login() -> None:
    assert client.get("/api/v1/depts").status_code == 401
    assert client.get("/api/v1/depts/tree").status_code == 401


def test_admin_list_tree_and_create_child(admin_headers: dict[str, str]) -> None:
    tree = client.get("/api/v1/depts/tree", headers=admin_headers)
    assert tree.status_code == 200
    roots = tree.json()["data"]
    assert len(roots) >= 1
    root_id = roots[0]["id"]

    created = client.post(
        "/api/v1/depts",
        headers=admin_headers,
        json={"name": f"F1子部门-{uuid.uuid4().hex[:6]}", "parent_id": root_id},
    )
    assert created.status_code == 200
    child_id = created.json()["data"]["id"]

    detail = client.get(f"/api/v1/depts/{child_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["parent_id"] == root_id

    listed = client.get("/api/v1/depts?page=1&page_size=100", headers=admin_headers)
    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["total"] >= 1 and isinstance(body["items"], list)
    # 可见性已由详情断言；列表只验分页结构（库中可能有大量历史测试部门）


def test_delete_dept_with_child_returns_409(admin_headers: dict[str, str]) -> None:
    tree = client.get("/api/v1/depts/tree", headers=admin_headers).json()["data"]
    root_id = tree[0]["id"]

    parent = client.post(
        "/api/v1/depts",
        headers=admin_headers,
        json={"name": f"F1父-{uuid.uuid4().hex[:6]}", "parent_id": root_id},
    ).json()["data"]
    client.post(
        "/api/v1/depts",
        headers=admin_headers,
        json={"name": f"F1子-{uuid.uuid4().hex[:6]}", "parent_id": parent["id"]},
    )

    deleted = client.delete(f"/api/v1/depts/{parent['id']}", headers=admin_headers)
    assert deleted.status_code == 409
    assert deleted.json()["code"] == 40900


def test_delete_root_with_admin_user_returns_409(admin_headers: dict[str, str]) -> None:
    """seed 根部门下挂着初始管理员，软删应 409。"""
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        assert root is not None
        root_id = str(root.id)

    deleted = client.delete(f"/api/v1/depts/{root_id}", headers=admin_headers)
    assert deleted.status_code == 409
    assert deleted.json()["code"] == 40900
