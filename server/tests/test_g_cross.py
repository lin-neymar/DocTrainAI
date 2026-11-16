"""S7 / G：阶段 1 交叉补测（对齐 SERVER_SPEC「阶段 1 测试」清单）。

覆盖：登录与 401、缺码 403、audience 外 404、audience 子树可读、
仅 data:scope:all 不旁路阅读、data:read:all 旁路全量阅读、挂课不越权、品牌公开、
无 system:update 不能改品牌、本人主题、四角色权限抽检。不引入阶段 2 依赖。
"""

from __future__ import annotations

import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.system.dept import Dept
from app.models.system.doc import DocAudienceDept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from scripts.seed import run_seed
from scripts.seed_data import ROLES

client = TestClient(app)

_MD = b"# g-cross\n"
_PASSWORD = "GCrossPass1!"


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _login(username: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin_headers() -> dict[str, str]:
    return _login(settings.init_admin_username, settings.init_admin_password)


def _root_and_branch() -> tuple[str, str]:
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        assert root is not None
        branch = Dept(
            name=f"G-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False
        )
        session.add(branch)
        session.commit()
        return str(root.id), str(branch.id)


def _create_user_with_role(
    *, username: str, role_code: str, dept_id: str
) -> None:
    with SessionLocal() as session:
        role = session.scalar(
            select(Role).where(Role.code == role_code, Role.is_deleted.is_(False))
        )
        assert role is not None, role_code
        user = User(
            username=username,
            password_hash=_hash(_PASSWORD),
            dept_id=uuid.UUID(dept_id),
            is_deleted=False,
        )
        session.add(user)
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()


@pytest.fixture(scope="module")
def seeded() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")


# --- 登录 / 401 / 403 ---


def test_g_login_success_and_failure(seeded: None) -> None:
    ok = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    assert ok.status_code == 200
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["access_token"]

    bad = client.post(
        "/api/v1/auth/login",
        json={"username": settings.init_admin_username, "password": "nope"},
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == 40100


def test_g_no_token_401(seeded: None) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/docs").status_code == 401
    assert client.get("/api/v1/courses").status_code == 401
    assert client.get("/api/v1/system/settings").status_code == 401


def test_g_staff_forbidden_on_admin_apis(seeded: None) -> None:
    root_id, _ = _root_and_branch()
    username = f"g_staff_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(username=username, role_code="staff", dept_id=root_id)
    headers = _login(username, _PASSWORD)

    # staff 无 system:update / role:assign_perm / doc:create
    assert (
        client.put(
            "/api/v1/system/settings",
            headers=headers,
            json={"site_name": "hack", "login_subtitle": "x"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/permissions", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/docs",
            headers=headers,
            data={"title": "x", "dept_id": root_id},
            files={"file": ("x.md", _MD, "text/markdown")},
        ).status_code
        == 403
    )


# --- audience / scope:all ---


def test_g_audience_outside_404_and_subtree_readable(seeded: None) -> None:
    admin = _admin_headers()
    root_id, branch_id = _root_and_branch()
    username = f"g_aud_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(username=username, role_code="staff", dept_id=branch_id)
    staff = _login(username, _PASSWORD)
    # 公司管理员（无 data:read:all）在根：audience 不覆盖根时读不到
    comp_username = f"g_comp_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(
        username=comp_username, role_code="company_admin", dept_id=root_id
    )
    comp_admin = _login(comp_username, _PASSWORD)

    # audience 仅分公司 → 员工可读；无 read:all 的公司管理员不可读；超管凭 data:read:all 可读
    created = client.post(
        "/api/v1/docs",
        headers=admin,
        data={
            "title": f"g-aud-{uuid.uuid4().hex[:6]}",
            "dept_id": root_id,
            "audience_dept_ids": json.dumps([branch_id]),
        },
        files={"file": ("g.md", _MD, "text/markdown")},
    )
    assert created.status_code == 200
    doc_id = created.json()["data"]["id"]

    assert client.get(f"/api/v1/docs/{doc_id}", headers=staff).status_code == 200
    assert client.get(f"/api/v1/docs/{doc_id}", headers=comp_admin).status_code == 404
    assert client.get(f"/api/v1/docs/{doc_id}", headers=admin).status_code == 200

    # 扩到根后公司管理员可读
    upd = client.put(
        f"/api/v1/docs/{doc_id}",
        headers=admin,
        json={"audience_dept_ids": [root_id]},
    )
    assert upd.status_code == 200
    assert client.get(f"/api/v1/docs/{doc_id}", headers=comp_admin).status_code == 200


def test_g_read_all_bypasses_audience(seeded: None) -> None:
    """超管有 data:read:all：audience 未覆盖其所在部门也可读。"""
    admin = _admin_headers()
    root_id, branch_id = _root_and_branch()
    created = client.post(
        "/api/v1/docs",
        headers=admin,
        data={
            "title": f"g-bypass-{uuid.uuid4().hex[:6]}",
            "dept_id": root_id,
            "audience_dept_ids": json.dumps([branch_id]),
        },
        files={"file": ("b.md", _MD, "text/markdown")},
    )
    assert created.status_code == 200
    doc_id = created.json()["data"]["id"]
    assert client.get(f"/api/v1/docs/{doc_id}", headers=admin).status_code == 200


# --- 挂课不越权 ---


def test_g_attach_doc_must_be_visible_to_operator(seeded: None) -> None:
    admin = _admin_headers()
    root_id, branch_id = _root_and_branch()

    created_doc = client.post(
        "/api/v1/docs",
        headers=admin,
        data={
            "title": f"g-attach-{uuid.uuid4().hex[:6]}",
            "dept_id": root_id,
            "audience_dept_ids": json.dumps([branch_id]),
        },
        files={"file": ("a.md", _MD, "text/markdown")},
    )
    assert created_doc.status_code == 200
    doc_id = created_doc.json()["data"]["id"]

    # 无 data:read:all 的公司管理员在根：audience 仅分公司 → 读不到该文档
    comp_username = f"g_att_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(
        username=comp_username, role_code="company_admin", dept_id=root_id
    )
    comp_admin = _login(comp_username, _PASSWORD)
    assert client.get(f"/api/v1/docs/{doc_id}", headers=comp_admin).status_code == 404

    course = client.post(
        "/api/v1/courses",
        headers=comp_admin,
        json={
            "title": f"g-course-{uuid.uuid4().hex[:6]}",
            "dept_id": root_id,
            "audience_dept_ids": [root_id],
        },
    )
    assert course.status_code == 200
    course_id = course.json()["data"]["id"]

    attach = client.put(
        f"/api/v1/courses/{course_id}/docs",
        headers=comp_admin,
        json={"doc_ids": [doc_id]},
    )
    assert attach.status_code == 404
    assert attach.json()["code"] == 40400


# --- 品牌 / 主题 ---


def test_g_brand_public_and_theme_self(seeded: None) -> None:
    brand = client.get("/api/v1/system/brand")
    assert brand.status_code == 200
    assert brand.json()["data"]["site_name"]

    root_id, _ = _root_and_branch()
    username = f"g_theme_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(username=username, role_code="staff", dept_id=root_id)
    headers = _login(username, _PASSWORD)

    theme = client.put(
        "/api/v1/auth/me/theme",
        headers=headers,
        json={"theme_primary": "#336699"},
    )
    assert theme.status_code == 200
    assert theme.json()["data"]["theme_primary"] == "#336699"

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["data"]["theme_primary"] == "#336699"

    # 无 system:update 不能改品牌
    denied = client.put(
        "/api/v1/system/settings",
        headers=headers,
        json={"site_name": "被拒", "login_subtitle": "x"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == 40300


# --- 四角色抽检（只认权限码集合，角色 code 仅用于 seed 建用户） ---


def test_g_four_roles_permission_spot_check(seeded: None) -> None:
    root_id, _ = _root_and_branch()
    expected = {code: set(perms) for code, _, perms in ROLES}

    for role_code, want in expected.items():
        username = f"g_{role_code}_{uuid.uuid4().hex[:6]}"
        _create_user_with_role(
            username=username, role_code=role_code, dept_id=root_id
        )
        headers = _login(username, _PASSWORD)
        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        got = set(me.json()["data"]["permission_codes"])
        assert got == want, f"{role_code}: missing={want - got} extra={got - want}"

    # 关键断言：公司官无 system:* / scope:all / read:all；部门官无 dept 写与配权；员工仅四码
    assert "system:update" not in expected["company_admin"]
    assert "data:scope:all" not in expected["company_admin"]
    assert "data:read:all" not in expected["company_admin"]
    assert "data:read:all" in expected["super_admin"]
    assert "dept:create" not in expected["dept_admin"]
    assert "role:assign_perm" not in expected["dept_admin"]
    assert expected["staff"] == {"dept:read", "doc:read", "course:read", "agent:chat"}


def test_g_dept_admin_audience_forced_ignores_client(seeded: None) -> None:
    """部门官发布：客户端传根 audience 被忽略，落库为本部门。"""
    root_id, branch_id = _root_and_branch()
    username = f"g_da_{uuid.uuid4().hex[:8]}"
    _create_user_with_role(
        username=username, role_code="dept_admin", dept_id=branch_id
    )
    headers = _login(username, _PASSWORD)

    created = client.post(
        "/api/v1/docs",
        headers=headers,
        data={
            "title": f"g-da-{uuid.uuid4().hex[:6]}",
            "dept_id": branch_id,
            "audience_dept_ids": json.dumps([root_id]),
        },
        files={"file": ("da.md", _MD, "text/markdown")},
    )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["audience_dept_ids"] == [branch_id]

    with SessionLocal() as session:
        rows = list(
            session.scalars(
                select(DocAudienceDept.dept_id).where(
                    DocAudienceDept.doc_id == uuid.UUID(body["id"])
                )
            ).all()
        )
    assert rows == [uuid.UUID(branch_id)]
