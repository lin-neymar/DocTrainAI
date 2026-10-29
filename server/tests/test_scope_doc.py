"""E-C：get_visible_doc_ids 集成测试（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.doc import Doc
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.system import scope_service
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_doc(
    session,
    *,
    title: str,
    dept_id: uuid.UUID,
    uploaded_by: uuid.UUID,
) -> Doc:
    doc = Doc(
        title=title,
        dept_id=dept_id,
        original_filename=f"{title}.pdf",
        extension="pdf",
        size_bytes=100,
        storage_key=f"test/{uuid.uuid4()}.pdf",
        sha256="b" * 64,
        uploaded_by=uploaded_by,
        is_deleted=False,
    )
    session.add(doc)
    session.flush()
    return doc


@pytest.fixture
def seeded_session():
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            yield session
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")


def test_admin_sees_docs_across_depts(seeded_session) -> None:
    """超管有 doc:read + data:scope:all → 各分支文档均可见。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False)))
    assert root is not None

    child = Dept(name="E-C子部门", parent_id=root.id, is_deleted=False)
    session.add(child)
    session.flush()

    d1 = _create_doc(session, title="ec-root", dept_id=root.id, uploaded_by=admin.id)
    d2 = _create_doc(session, title="ec-child", dept_id=child.id, uploaded_by=admin.id)
    session.commit()

    visible = set(scope_service.get_visible_doc_ids(session, admin.id))
    assert d1.id in visible
    assert d2.id in visible


def test_staff_sees_docs_only_in_accessible_depts(seeded_session) -> None:
    """staff 有 doc:read、无 scope:all → 只见本部门支路上的文档。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert admin is not None and staff_role is not None

    root = session.scalar(select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False)))
    assert root is not None
    branch_a = Dept(name="E-C分支A", parent_id=root.id, is_deleted=False)
    branch_b = Dept(name="E-C分支B", parent_id=root.id, is_deleted=False)
    session.add_all([branch_a, branch_b])
    session.flush()

    staff = User(
        username=f"staff_ec_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=branch_a.id,
        is_deleted=False,
    )
    session.add(staff)
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))

    doc_a = _create_doc(session, title="in-a", dept_id=branch_a.id, uploaded_by=admin.id)
    doc_b = _create_doc(session, title="in-b", dept_id=branch_b.id, uploaded_by=admin.id)
    session.commit()

    visible = set(scope_service.get_visible_doc_ids(session, staff.id))
    assert doc_a.id in visible
    assert doc_b.id not in visible


def test_user_without_doc_read_sees_no_docs(seeded_session) -> None:
    """无任何角色 → 无 doc:read → 可见文档恒为空（即使部门下有文档）。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False)))
    assert root is not None

    _create_doc(session, title="hidden", dept_id=root.id, uploaded_by=admin.id)

    bare = User(
        username=f"noperm_ec_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=root.id,
        is_deleted=False,
    )
    session.add(bare)
    session.commit()

    assert scope_service.get_visible_doc_ids(session, bare.id) == []
