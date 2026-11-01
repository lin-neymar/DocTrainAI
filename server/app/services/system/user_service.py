"""用户业务：范围内 CRUD、角色绑定、管理员重置密码。"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.system.dept import Dept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.system import scope_service
from app.utils.pagination import page_offset


# 实现：查询用户已绑定的角色 id 列表
def _role_ids_of(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        ).all()
    )


# 实现：用户转响应 dict（不含密码哈希）
def _to_dict(session: Session, user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "dept_id": str(user.dept_id),
        "role_ids": [str(rid) for rid in _role_ids_of(session, user.id)],
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# 实现：取操作者可访问部门集合
def _accessible_set(session: Session, operator_id: uuid.UUID) -> set[uuid.UUID]:
    return set(scope_service.get_accessible_dept_ids(session, operator_id))


# 实现：断言部门存在且在操作者数据范围内
def _require_dept_in_scope(
    session: Session, operator_id: uuid.UUID, dept_id: uuid.UUID
) -> None:
    dept = session.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
    )
    if dept is None or dept_id not in _accessible_set(session, operator_id):
        raise NotFoundError("部门不存在")


# 实现：按 id 取未删用户，且其部门须在操作者范围内（否则 404）
def _require_user_in_scope(
    session: Session, operator_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = session.scalar(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )
    if user is None or user.dept_id not in _accessible_set(session, operator_id):
        raise NotFoundError("用户不存在")
    return user


# 实现：用户名在未删除记录中唯一
def _ensure_username_available(
    session: Session, username: str, *, exclude_user_id: uuid.UUID | None = None
) -> None:
    stmt = select(User).where(User.username == username, User.is_deleted.is_(False))
    existing = session.scalar(stmt)
    if existing is not None and existing.id != exclude_user_id:
        raise ConflictError("用户名已存在")


# 实现：校验角色均存在且未删除，并整体替换 user_role
def _replace_roles(
    session: Session, user_id: uuid.UUID, role_ids: list[uuid.UUID]
) -> None:
    if role_ids:
        found = set(
            session.scalars(
                select(Role.id).where(
                    Role.id.in_(role_ids),
                    Role.is_deleted.is_(False),
                )
            ).all()
        )
        missing = set(role_ids) - found
        if missing:
            raise NotFoundError("角色不存在")

    session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for rid in role_ids:
        session.add(UserRole(user_id=user_id, role_id=rid))


# 实现：转义 ILIKE 通配符，避免用户输入 %/_ 扩大匹配
def _ilike_pattern(raw: str) -> str:
    escaped = (
        raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


# 实现：分页列出数据范围内的用户（可选 username 模糊筛选）
def list_users(
    session: Session,
    *,
    operator_id: uuid.UUID,
    page: int,
    page_size: int,
    username: str | None = None,
) -> tuple[list[dict], int]:
    accessible = list(_accessible_set(session, operator_id))
    if not accessible:
        return [], 0

    conditions = [
        User.is_deleted.is_(False),
        User.dept_id.in_(accessible),
    ]
    if username is not None:
        cleaned = username.strip()
        if cleaned:
            conditions.append(
                User.username.ilike(_ilike_pattern(cleaned), escape="\\")
            )

    total = (
        session.scalar(select(func.count()).select_from(User).where(*conditions))
        or 0
    )
    rows = session.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.created_at, User.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(session, u) for u in rows], int(total)


# 实现：用户详情
def get_user(
    session: Session, *, operator_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    user = _require_user_in_scope(session, operator_id, user_id)
    return _to_dict(session, user)


# 实现：创建用户（含角色绑定）
def create_user(
    session: Session,
    *,
    operator_id: uuid.UUID,
    username: str,
    password: str,
    dept_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> dict:
    _require_dept_in_scope(session, operator_id, dept_id)
    _ensure_username_available(session, username)

    user = User(
        username=username,
        password_hash=hash_password(password),
        dept_id=dept_id,
        is_deleted=False,
    )
    session.add(user)
    session.flush()
    _replace_roles(session, user.id, role_ids)
    session.commit()
    session.refresh(user)
    return _to_dict(session, user)


# 实现：更新用户名、部门、角色
def update_user(
    session: Session,
    *,
    operator_id: uuid.UUID,
    user_id: uuid.UUID,
    username: str | None,
    dept_id: uuid.UUID | None,
    role_ids: list[uuid.UUID] | None,
) -> dict:
    user = _require_user_in_scope(session, operator_id, user_id)

    if username is not None:
        _ensure_username_available(session, username, exclude_user_id=user.id)
        user.username = username

    if dept_id is not None:
        _require_dept_in_scope(session, operator_id, dept_id)
        user.dept_id = dept_id

    if role_ids is not None:
        _replace_roles(session, user.id, role_ids)

    session.commit()
    session.refresh(user)
    return _to_dict(session, user)


# 实现：管理员重置密码
def reset_password(
    session: Session,
    *,
    operator_id: uuid.UUID,
    user_id: uuid.UUID,
    new_password: str,
) -> None:
    user = _require_user_in_scope(session, operator_id, user_id)
    user.password_hash = hash_password(new_password)
    session.commit()


# 实现：软删除用户（不可删自己）
def soft_delete_user(
    session: Session, *, operator_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    if operator_id == user_id:
        raise ConflictError("不能删除当前登录用户")
    user = _require_user_in_scope(session, operator_id, user_id)
    user.is_deleted = True
    session.commit()


# 实现：批量软删除（先全部校验再提交；跳过自己；仅含自己时 409）
def soft_delete_users(
    session: Session, *, operator_id: uuid.UUID, user_ids: list[uuid.UUID]
) -> dict:
    unique_ids = list(dict.fromkeys(user_ids))
    skipped_self = operator_id in unique_ids
    targets = [uid for uid in unique_ids if uid != operator_id]
    if not targets:
        raise ConflictError("不能删除当前登录用户")

    users: list[User] = []
    for uid in targets:
        users.append(_require_user_in_scope(session, operator_id, uid))

    for user in users:
        user.is_deleted = True
    session.commit()
    return {
        "deleted_count": len(users),
        "skipped_self": skipped_self,
    }
