"""E-B：get_accessible_dept_ids 集成测试（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.system import scope_service
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@pytest.fixture
def seeded_session():
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            yield session
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")


def test_admin_with_scope_all_sees_all_depts(seeded_session) -> None:
    """超管含 data:scope:all → 任意新建子部门也在可访问集合内。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None

    root = session.scalar(select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False)))
    assert root is not None
    child = Dept(name="E-B子部门", parent_id=root.id, is_deleted=False)
    session.add(child)
    session.commit()

    accessible = set(scope_service.get_accessible_dept_ids(session, admin.id))
    assert root.id in accessible
    assert child.id in accessible


def test_staff_sees_own_branch_subtree_only(seeded_session) -> None:
    """普通员工无 scope:all → 仅本部门及下级，不含兄弟分支。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert admin is not None and staff_role is not None

    root = session.scalar(select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False)))
    assert root is not None

    branch_a = Dept(name="E-B分支A", parent_id=root.id, is_deleted=False)
    branch_b = Dept(name="E-B分支B", parent_id=root.id, is_deleted=False)
    session.add_all([branch_a, branch_b])
    session.flush()

    child_under_a = Dept(name="E-B-A1", parent_id=branch_a.id, is_deleted=False)
    session.add(child_under_a)
    session.flush()

    staff = User(
        username=f"staff_eb_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=branch_a.id,
        is_deleted=False,
    )
    session.add(staff)
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))
    session.commit()

    accessible = set(scope_service.get_accessible_dept_ids(session, staff.id))
    assert branch_a.id in accessible
    assert child_under_a.id in accessible
    assert branch_b.id not in accessible
    assert root.id not in accessible
