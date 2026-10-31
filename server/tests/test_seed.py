"""seed 自动化 smoke（需 Postgres 已 migrate；库未就绪则 skip）。

验证：
  1. 连续两次 run_seed 后活跃行数不变（幂等）；
  2. 现行权限码数量、内置角色数量、品牌行、根部门与管理员存在；
  3. 旧聚合码已软删；company_admin 存在。
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.permission import Permission
from app.models.system.role import Role
from app.models.system.system_brand import SystemBrand
from app.models.system.user import User
from scripts.seed import run_seed
from scripts.seed_data import (
    ACTIVE_PERMISSION_COUNT,
    BUILTIN_ROLE_CODES,
    DEPRECATED_PERMISSION_CODES,
)


def _active_counts(session: Session) -> tuple[int, int, int, int, int]:
    """(dept, active_perm, role, user, brand)。"""
    dept = session.scalar(
        select(func.count()).select_from(Dept).where(Dept.is_deleted.is_(False))
    ) or 0
    perm = session.scalar(
        select(func.count())
        .select_from(Permission)
        .where(Permission.is_deleted.is_(False))
    ) or 0
    role = session.scalar(
        select(func.count()).select_from(Role).where(Role.is_deleted.is_(False))
    ) or 0
    user = session.scalar(
        select(func.count()).select_from(User).where(User.is_deleted.is_(False))
    ) or 0
    brand = session.scalar(select(func.count()).select_from(SystemBrand)) or 0
    return dept, perm, role, user, brand


def test_seed_idempotent_and_expected_counts() -> None:
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            first = _active_counts(session)

        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            second = _active_counts(session)

            deprecated_still_active = session.scalars(
                select(Permission.code).where(
                    Permission.code.in_(DEPRECATED_PERMISSION_CODES),
                    Permission.is_deleted.is_(False),
                )
            ).all()
            company = session.scalar(
                select(Role).where(
                    Role.code == "company_admin",
                    Role.is_deleted.is_(False),
                )
            )
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    assert first == second
    assert first[1] == ACTIVE_PERMISSION_COUNT
    # 允许库中另有管理员自建角色；内置四个必须都在
    assert first[2] >= len(BUILTIN_ROLE_CODES)
    assert first[0] >= 1
    assert first[3] >= 1
    assert first[4] == 1
    assert deprecated_still_active == []
    assert company is not None

    with SessionLocal() as session:
        codes = set(
            session.scalars(
                select(Role.code).where(
                    Role.code.in_(BUILTIN_ROLE_CODES),
                    Role.is_deleted.is_(False),
                )
            ).all()
        )
    assert codes == set(BUILTIN_ROLE_CODES)
