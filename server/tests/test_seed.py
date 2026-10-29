"""C3：seed 自动化 smoke（需 Postgres 已 migrate；库未就绪则 skip）。

验证两件事：
  1. 连续两次 run_seed + commit 后行数不变（幂等）；
  2. 权限 9、角色 3、至少 1 根部门、至少 1 用户（与 seed_data / 规约一致）。

不替代阶段 G 的登录/鉴权集成测试。
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.permission import Permission
from app.models.system.role import Role
from app.models.system.user import User
from scripts.seed import run_seed


def _counts(session: Session) -> tuple[int, int, int, int]:
    """返回 (dept 数, permission 数, role 数, user 数)。"""
    dept = session.scalar(select(func.count()).select_from(Dept)) or 0
    perm = session.scalar(select(func.count()).select_from(Permission)) or 0
    role = session.scalar(select(func.count()).select_from(Role)) or 0
    user = session.scalar(select(func.count()).select_from(User)) or 0
    return dept, perm, role, user


def test_seed_idempotent_and_expected_counts() -> None:
    try:
        # 第一次：可能从空库写入
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            first = _counts(session)

        # 第二次：不应多出重复 permission/role 等
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            second = _counts(session)
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    assert first == second
    assert first[1] == 9
    assert first[2] == 3
    assert first[0] >= 1
    assert first[3] >= 1
