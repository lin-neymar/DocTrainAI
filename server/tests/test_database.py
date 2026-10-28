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
from app.models.system.dept import Dept
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
