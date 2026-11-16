"""S5：get_visible_course_ids 与课程 audience（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.system.course import Course, CourseAudienceDept
from app.models.system.dept import Dept
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.user import User, UserRole
from app.services.system import scope_service
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_course(
    session,
    *,
    title: str,
    dept_id: uuid.UUID,
    audience_dept_ids: list[uuid.UUID] | None = None,
) -> Course:
    course = Course(
        title=title,
        description=None,
        dept_id=dept_id,
        is_deleted=False,
    )
    session.add(course)
    session.flush()
    for aid in audience_dept_ids if audience_dept_ids is not None else [dept_id]:
        session.add(CourseAudienceDept(course_id=course.id, dept_id=aid))
    return course


@pytest.fixture
def seeded_session():
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            yield session
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")


def test_staff_sees_course_in_audience_subtree(seeded_session) -> None:
    session = seeded_session
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert staff_role is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    branch_a = Dept(
        name=f"SC-A-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False
    )
    branch_b = Dept(
        name=f"SC-B-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False
    )
    session.add_all([branch_a, branch_b])
    session.flush()

    staff = User(
        username=f"staff_sc_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=branch_a.id,
        is_deleted=False,
    )
    session.add(staff)
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))

    c_a = _create_course(
        session, title="ca", dept_id=branch_a.id, audience_dept_ids=[branch_a.id]
    )
    c_b = _create_course(
        session, title="cb", dept_id=branch_b.id, audience_dept_ids=[branch_b.id]
    )
    session.commit()

    visible = set(scope_service.get_visible_course_ids(session, staff.id))
    assert c_a.id in visible
    assert c_b.id not in visible


def test_scope_all_without_read_all_does_not_reveal_course(seeded_session) -> None:
    """仅 data:scope:all + course:read（无 data:read:all）→ 不旁路；超管凭 read:all 可见。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    leaf = Dept(
        name=f"SC-leaf-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False
    )
    session.add(leaf)
    session.flush()

    course = _create_course(
        session, title="hidden-course", dept_id=leaf.id, audience_dept_ids=[leaf.id]
    )

    # 自定义角色：course:read + data:scope:all，但不含 data:read:all
    role = Role(
        code=f"scope_only_{uuid.uuid4().hex[:8]}", name="范围角色", is_deleted=False
    )
    session.add(role)
    session.flush()
    for code in ("course:read", "data:scope:all"):
        perm = session.scalar(
            select(Permission).where(
                Permission.code == code, Permission.is_deleted.is_(False)
            )
        )
        assert perm is not None
        session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    user = User(
        username=f"scopeonly_sc_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=root.id,
        is_deleted=False,
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()

    visible = set(scope_service.get_visible_course_ids(session, user.id))
    assert course.id not in visible

    # 超管有 data:read:all → 旁路可见
    admin_visible = set(scope_service.get_visible_course_ids(session, admin.id))
    assert course.id in admin_visible
