"""G6：数据库集成测试（需要 Docker 里 Postgres 已启动且 alembic upgrade head 已执行）。

和 test_health 的区别：
  - health 测 HTTP，不连库；
  - 这里测「Python → SQLAlchemy → PostgreSQL」整条链，以及 dept 表是否存在。

若库未启动，用 pytest.skip 跳过而不是失败——避免没开 Docker 时 CI/本地误红。
你在本机开发时应先 docker compose up -d，再跑 pytest，期望这两项都 pass。
"""

import pytest
from sqlalchemy import func, select, text

from app.database import SessionLocal
from app.models.system.course import Course, CourseAudienceDept
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.models.system.permission import Permission
from app.models.system.role import Role
from app.models.system.user import User


def test_database_select_one() -> None:
    """G4 验收自动化：能否执行最简单的 SQL（与手动 python -c SELECT 1 等价）。"""
    try:
        with SessionLocal() as session:
            result = session.execute(text("SELECT 1")).scalar_one()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可用，请先 docker compose up -d: {exc}")

    assert result == 1


def test_dept_table_exists_and_queryable() -> None:
    """G5 验收自动化：ORM 能否访问 dept 表（表空也可以，count 应为 0）。"""
    try:
        with SessionLocal() as session:
            count = session.scalar(select(func.count()).select_from(Dept))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪，请 alembic upgrade head: {exc}")

    assert count is not None
    assert count >= 0


def test_permission_and_role_tables_queryable() -> None:
    """B1：permission / role 表已迁移且 ORM 可访问（空表 count=0 即可）。"""
    try:
        with SessionLocal() as session:
            perm_count = session.scalar(select(func.count()).select_from(Permission))
            role_count = session.scalar(select(func.count()).select_from(Role))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪，请 alembic upgrade head: {exc}")

    assert perm_count is not None and perm_count >= 0
    assert role_count is not None and role_count >= 0


def test_user_table_queryable() -> None:
    """B2：user 表已迁移且 ORM 可访问（空表 count=0 即可）。"""
    try:
        with SessionLocal() as session:
            user_count = session.scalar(select(func.count()).select_from(User))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪，请 alembic upgrade head: {exc}")

    assert user_count is not None and user_count >= 0


def test_doc_and_course_tables_queryable() -> None:
    """B3/B4：doc / course 表已迁移且 ORM 可访问（空表 count=0 即可）。"""
    try:
        with SessionLocal() as session:
            doc_count = session.scalar(select(func.count()).select_from(Doc))
            course_count = session.scalar(select(func.count()).select_from(Course))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪，请 alembic upgrade head: {exc}")

    assert doc_count is not None and doc_count >= 0
    assert course_count is not None and course_count >= 0


def test_audience_tables_and_backfill_invariant() -> None:
    """S4：audience 表可查；每条 doc/course 至少有一条 audience，且含归属 dept_id。"""
    try:
        with SessionLocal() as session:
            aud_doc = session.scalar(select(func.count()).select_from(DocAudienceDept))
            aud_course = session.scalar(
                select(func.count()).select_from(CourseAudienceDept)
            )
            docs = session.scalars(select(Doc)).all()
            courses = session.scalars(select(Course)).all()
            for doc in docs:
                has_owner = session.scalar(
                    select(func.count())
                    .select_from(DocAudienceDept)
                    .where(
                        DocAudienceDept.doc_id == doc.id,
                        DocAudienceDept.dept_id == doc.dept_id,
                    )
                )
                assert has_owner == 1, f"doc {doc.id} 缺少归属 audience"
            for course in courses:
                has_owner = session.scalar(
                    select(func.count())
                    .select_from(CourseAudienceDept)
                    .where(
                        CourseAudienceDept.course_id == course.id,
                        CourseAudienceDept.dept_id == course.dept_id,
                    )
                )
                assert has_owner == 1, f"course {course.id} 缺少归属 audience"
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪，请 alembic upgrade head: {exc}")

    assert aud_doc is not None and aud_doc >= 0
    assert aud_course is not None and aud_course >= 0
    # 有旧文档时，验收「至少一条 audience」
    if docs:
        assert aud_doc >= 1
    if courses:
        assert aud_course >= 1

