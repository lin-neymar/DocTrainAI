"""require_permission 集成测试。

用临时 mini-app 挂一条假路由，避免污染 app.main 的路由表。
验证 401（未登录）→ 403（已登录但缺码）→ 200（有码） 的层次。
"""

import uuid
from typing import Annotated

import bcrypt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.core.deps import require_permission
from app.core.handlers import register_exception_handlers
from app.core.response import success
from app.database import SessionLocal, get_db
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.schemas.system.auth import LoginRequest
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _login_token(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/probe/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest.fixture
def probe_client():
    """带 login 探针 + 受 dept:create 保护的路由。"""
    from app.api.system.auth import login as auth_login

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/probe/login")
    def probe_login(body: LoginRequest, db=Depends(get_db)):
        return auth_login(body, db)

    @app.get("/probe/dept-create")
    def probe_dept_create(
        _user: Annotated[User, Depends(require_permission("dept:create"))],
    ) -> dict:
        return success({"ok": True})

    with SessionLocal() as session:
        try:
            run_seed(session)
            session.commit()
        except Exception as exc:
            pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    return TestClient(app)


def test_require_permission_no_token_401(probe_client: TestClient) -> None:
    response = probe_client.get("/probe/dept-create")
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_require_permission_staff_403(probe_client: TestClient) -> None:
    with SessionLocal() as session:
        staff_role = session.scalar(
            select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
        )
        root_dept_id = session.scalar(
            select(User.dept_id).where(User.username == settings.init_admin_username)
        )
        assert staff_role is not None and root_dept_id is not None

        staff = User(
            username=f"staff_ea_{uuid.uuid4().hex[:8]}",
            password_hash=_hash_password("staff-pass"),
            dept_id=root_dept_id,
            is_deleted=False,
        )
        session.add(staff)
        session.flush()
        session.add(UserRole(user_id=staff.id, role_id=staff_role.id))
        session.commit()
        staff_name = staff.username

    token = _login_token(probe_client, staff_name, "staff-pass")
    response = probe_client.get(
        "/probe/dept-create",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40300


def test_require_permission_admin_200(probe_client: TestClient) -> None:
    token = _login_token(
        probe_client,
        settings.init_admin_username,
        settings.init_admin_password,
    )
    response = probe_client.get(
        "/probe/dept-create",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
