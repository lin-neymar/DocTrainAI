"""S5：get_visible_course_ids 与课程 audience（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.system.course import Course, CourseAudienceDept
from app.models.system.dept import Dept
from app.models.system.role import Role
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


def test_scope_all_alone_does_not_reveal_course(seeded_session) -> None:
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
    session.commit()

    visible = set(scope_service.get_visible_course_ids(session, admin.id))
    assert course.id not in visible
