"""F5：课程 API 集成测试（需 Postgres + seed）。"""

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

_MD_BYTES = b"# course fixture\n"


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


def _upload_doc(admin_headers: dict[str, str], *, dept_id: str, title: str) -> str:
    resp = client.post(
        "/api/v1/docs",
        headers=admin_headers,
        data={"title": title, "dept_id": dept_id},
        files={"file": (f"{title}.md", _MD_BYTES, "text/markdown")},
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def test_courses_require_auth() -> None:
    assert client.get("/api/v1/courses").status_code == 401


def test_list_courses_filter_by_title(admin_headers: dict[str, str]) -> None:
    """列表可选 title 模糊筛选；仅匹配可见课程标题。"""
    root_id = _root_dept_id()
    marker = uuid.uuid4().hex[:8]
    title_hit = f"课程命中-{marker}"
    title_miss = f"其它课程-{marker}"

    for title in (title_hit, title_miss):
        created = client.post(
            "/api/v1/courses",
            headers=admin_headers,
            json={"title": title, "dept_id": root_id},
        )
        assert created.status_code == 200, created.text

    listed = client.get(
        "/api/v1/courses",
        headers=admin_headers,
        params={"page": 1, "page_size": 100, "title": f"命中-{marker}"},
    )
    assert listed.status_code == 200
    titles = {item["title"] for item in listed.json()["data"]["items"]}
    assert title_hit in titles
    assert title_miss not in titles


def test_create_list_attach_docs_update_delete(admin_headers: dict[str, str]) -> None:
    root_id = _root_dept_id()
    title = f"入职课-{uuid.uuid4().hex[:8]}"
    doc_a = _upload_doc(admin_headers, dept_id=root_id, title=f"da-{uuid.uuid4().hex[:6]}")
    doc_b = _upload_doc(admin_headers, dept_id=root_id, title=f"db-{uuid.uuid4().hex[:6]}")

    created = client.post(
        "/api/v1/courses",
        headers=admin_headers,
        json={
            "title": title,
            "description": "新人必读",
            "dept_id": root_id,
        },
    )
    assert created.status_code == 200
    body = created.json()["data"]
    assert body["title"] == title
    assert body["doc_ids"] == []
    assert body["audience_dept_ids"] == [root_id]
    course_id = body["id"]

    listed = client.get("/api/v1/courses?page=1&page_size=100", headers=admin_headers)
    assert listed.status_code == 200
    assert course_id in {item["id"] for item in listed.json()["data"]["items"]}

    attached = client.put(
        f"/api/v1/courses/{course_id}/docs",
        headers=admin_headers,
        json={"doc_ids": [doc_a, doc_b]},
    )
    assert attached.status_code == 200
    assert set(attached.json()["data"]["doc_ids"]) == {doc_a, doc_b}

    # 整体替换：只留 doc_a
    replaced = client.put(
        f"/api/v1/courses/{course_id}/docs",
        headers=admin_headers,
        json={"doc_ids": [doc_a]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["data"]["doc_ids"] == [doc_a]

    updated = client.put(
        f"/api/v1/courses/{course_id}",
        headers=admin_headers,
        json={"title": title + "-改", "description": None},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == title + "-改"
    assert updated.json()["data"]["description"] is None

    deleted = client.delete(f"/api/v1/courses/{course_id}", headers=admin_headers)
    assert deleted.status_code == 200

    again = client.get(f"/api/v1/courses/{course_id}", headers=admin_headers)
    assert again.status_code == 404

    # 删课程不删文档
    doc_still = client.get(f"/api/v1/docs/{doc_a}", headers=admin_headers)
    assert doc_still.status_code == 200


def test_attach_unknown_doc_returns_404(admin_headers: dict[str, str]) -> None:
    root_id = _root_dept_id()
    created = client.post(
        "/api/v1/courses",
        headers=admin_headers,
        json={"title": f"c-{uuid.uuid4().hex[:6]}", "dept_id": root_id},
    )
    course_id = created.json()["data"]["id"]
    fake_doc = str(uuid.uuid4())

    resp = client.put(
        f"/api/v1/courses/{course_id}/docs",
        headers=admin_headers,
        json={"doc_ids": [fake_doc]},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40400
