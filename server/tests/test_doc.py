"""F4：文档 API 集成测试（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.system.dept import Dept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from scripts.seed import run_seed

client = TestClient(app)

_PDF_BYTES = b"%PDF-1.4\n%demo\n"
_MD_BYTES = b"# hello\n\nstage1 doc\n"


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


def _root_dept_id() -> str:
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        assert root is not None
        return str(root.id)


def test_docs_require_auth() -> None:
    assert client.get("/api/v1/docs").status_code == 401


def test_upload_list_download_update_delete(admin_headers: dict[str, str]) -> None:
    root_id = _root_dept_id()
    title = f"规章-{uuid.uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/docs",
        headers=admin_headers,
        data={"title": title, "dept_id": root_id},
        files={"file": ("rule.md", _MD_BYTES, "text/markdown")},
    )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["title"] == title
    assert body["extension"] == "md"
    assert body["sha256"]
    assert "storage_key" not in body
    doc_id = body["id"]

    listed = client.get("/api/v1/docs?page=1&page_size=100", headers=admin_headers)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["data"]["items"]}
    assert doc_id in ids

    detail = client.get(f"/api/v1/docs/{doc_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == title

    downloaded = client.get(f"/api/v1/docs/{doc_id}/file", headers=admin_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == _MD_BYTES

    updated = client.put(
        f"/api/v1/docs/{doc_id}",
        headers=admin_headers,
        json={"title": title + "-改"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == title + "-改"

    deleted = client.delete(f"/api/v1/docs/{doc_id}", headers=admin_headers)
    assert deleted.status_code == 200

    again = client.get(f"/api/v1/docs/{doc_id}", headers=admin_headers)
    assert again.status_code == 404


def test_reject_bad_extension_and_magic(admin_headers: dict[str, str]) -> None:
    root_id = _root_dept_id()

    bad_ext = client.post(
        "/api/v1/docs",
        headers=admin_headers,
        data={"title": "bad", "dept_id": root_id},
        files={"file": ("x.exe", b"MZ", "application/octet-stream")},
    )
    assert bad_ext.status_code == 422
    assert bad_ext.json()["code"] == 42200

    fake_pdf = client.post(
        "/api/v1/docs",
        headers=admin_headers,
        data={"title": "fake", "dept_id": root_id},
        files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert fake_pdf.status_code == 422
    assert fake_pdf.json()["code"] == 42200


def test_staff_cannot_see_other_branch_doc(admin_headers: dict[str, str]) -> None:
    """无 data:scope:all 的员工：兄弟部门文档详情应 404（不泄露存在性）。"""
    password = "staffpass1"
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        assert root is not None
        branch_a = Dept(name=f"A-{uuid.uuid4().hex[:6]}", parent_id=root.id)
        branch_b = Dept(name=f"B-{uuid.uuid4().hex[:6]}", parent_id=root.id)
        session.add_all([branch_a, branch_b])
        session.flush()

        staff_role = session.scalar(
            select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
        )
        assert staff_role is not None
        username = f"staff_f4_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            password_hash=bcrypt.hashpw(
                password.encode(), bcrypt.gensalt()
            ).decode(),
            dept_id=branch_a.id,
            is_deleted=False,
        )
        session.add(user)
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=staff_role.id))
        session.commit()
        branch_b_id = str(branch_b.id)

    # 管理员把文档挂到兄弟部门 B
    created = client.post(
        "/api/v1/docs",
        headers=admin_headers,
        data={"title": "仅B可见", "dept_id": branch_b_id},
        files={"file": ("b.pdf", _PDF_BYTES, "application/pdf")},
    )
    assert created.status_code == 200
    doc_id = created.json()["data"]["id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    staff_headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}"
    }

    resp = client.get(f"/api/v1/docs/{doc_id}", headers=staff_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == 40400

    # 超管仍可读
    admin_ok = client.get(f"/api/v1/docs/{doc_id}", headers=admin_headers)
    assert admin_ok.status_code == 200
