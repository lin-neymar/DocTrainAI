"""认证相关业务：查用户、验密、聚合 /me 需要的角色名与权限码。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.system.dept import Dept
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.user import User, UserRole


# 实现：登录校验（用户名+密码），成功返回 User
def authenticate_user(session: Session, username: str, password: str) -> User | None:
    """登录：用户名存在、未软删、密码正确才返回 User；否则 None（路由统一 401 文案）。"""
    user = session.scalar(
        select(User).where(
            User.username == username,
            User.is_deleted.is_(False),
        )
    )
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


# 实现：按 id 查询未软删用户
def get_active_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.scalar(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )


# 实现：按 id 查询未软删部门
def get_dept_by_id(session: Session, dept_id: uuid.UUID) -> Dept | None:
    return session.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
    )


# 实现：列出用户角色展示名（仅供 /me 展示）
def list_role_names_for_user(session: Session, user_id: uuid.UUID) -> list[str]:
    """角色展示名（给 /me 与前端展示）；鉴权只用 permission_codes，不用角色名。"""
    stmt = (
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.is_deleted.is_(False))
        .order_by(Role.name)
    )
    return list(session.scalars(stmt).all())


# 实现：聚合用户全部权限码（多角色并集）
def list_permission_codes_for_user(session: Session, user_id: uuid.UUID) -> list[str]:
    """用户所有角色的权限码并集（去重）；hasPermission / require_permission 的数据来源。"""
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            Permission.is_deleted.is_(False),
            Role.is_deleted.is_(False),
        )
        .distinct()
        .order_by(Permission.code)
    )
    return list(session.scalars(stmt).all())
