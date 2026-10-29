"""角色与权限码业务：CRUD、权限整体替换；只认权限码，不按角色 code 分支。"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.user import User, UserRole
from app.utils.pagination import page_offset


# 实现：查询角色已绑定的权限码列表（按 code 排序，便于前端稳定展示）
def _permission_codes_of(session: Session, role_id: uuid.UUID) -> list[str]:
    return list(
        session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id == role_id,
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.code)
        ).all()
    )


# 实现：角色转响应 dict（含 permission_codes）
def _to_dict(session: Session, role: Role) -> dict:
    return {
        "id": str(role.id),
        "code": role.code,
        "name": role.name,
        "permission_codes": _permission_codes_of(session, role.id),
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


# 实现：按 id 取未删角色，否则 404
def _require_role(session: Session, role_id: uuid.UUID) -> Role:
    role = session.scalar(
        select(Role).where(Role.id == role_id, Role.is_deleted.is_(False))
    )
    if role is None:
        raise NotFoundError("角色不存在")
    return role


# 实现：角色 code 在未删除记录中唯一
def _ensure_code_available(
    session: Session, code: str, *, exclude_role_id: uuid.UUID | None = None
) -> None:
    existing = session.scalar(
        select(Role).where(Role.code == code, Role.is_deleted.is_(False))
    )
    if existing is not None and existing.id != exclude_role_id:
        raise ConflictError("角色 code 已存在")


# 实现：把 permission_codes 解析为未删 Permission；未知码 → 404
def _resolve_permissions(
    session: Session, permission_codes: list[str]
) -> list[Permission]:
    if not permission_codes:
        return []
    # 去重但保序，避免中间表重复插入
    unique_codes = list(dict.fromkeys(permission_codes))
    found = list(
        session.scalars(
            select(Permission).where(
                Permission.code.in_(unique_codes),
                Permission.is_deleted.is_(False),
            )
        ).all()
    )
    found_codes = {p.code for p in found}
    missing = [c for c in unique_codes if c not in found_codes]
    if missing:
        raise NotFoundError(f"权限码不存在: {missing[0]}")
    return found


# 实现：整体替换 role_permission（先删后插）
def _replace_permissions(
    session: Session, role_id: uuid.UUID, permission_codes: list[str]
) -> None:
    perms = _resolve_permissions(session, permission_codes)
    session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for perm in perms:
        session.add(RolePermission(role_id=role_id, permission_id=perm.id))


# 实现：统计仍绑定该角色的未删除用户数
def _active_user_count(session: Session, role_id: uuid.UUID) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(UserRole)
            .join(User, User.id == UserRole.user_id)
            .where(
                UserRole.role_id == role_id,
                User.is_deleted.is_(False),
            )
        )
        or 0
    )


# 实现：从 DB 列出全部未删权限码（管理端选权限用，禁止写死 seed 常量）
def list_permissions(session: Session) -> list[dict]:
    rows = session.scalars(
        select(Permission)
        .where(Permission.is_deleted.is_(False))
        .order_by(Permission.code)
    ).all()
    return [
        {
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
        }
        for p in rows
    ]


# 实现：分页列出未删角色
def list_roles(
    session: Session, *, page: int, page_size: int
) -> tuple[list[dict], int]:
    total = (
        session.scalar(
            select(func.count())
            .select_from(Role)
            .where(Role.is_deleted.is_(False))
        )
        or 0
    )
    rows = session.scalars(
        select(Role)
        .where(Role.is_deleted.is_(False))
        .order_by(Role.created_at, Role.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(session, r) for r in rows], int(total)


# 实现：角色详情
def get_role(session: Session, *, role_id: uuid.UUID) -> dict:
    return _to_dict(session, _require_role(session, role_id))


# 实现：创建角色（仅 code/name；权限走 replace_permissions）
def create_role(session: Session, *, code: str, name: str) -> dict:
    _ensure_code_available(session, code)
    role = Role(code=code, name=name, is_deleted=False)
    session.add(role)
    session.commit()
    session.refresh(role)
    return _to_dict(session, role)


# 实现：更新角色 code / name
def update_role(
    session: Session,
    *,
    role_id: uuid.UUID,
    code: str | None,
    name: str | None,
) -> dict:
    role = _require_role(session, role_id)
    if code is not None:
        _ensure_code_available(session, code, exclude_role_id=role.id)
        role.code = code
    if name is not None:
        role.name = name
    session.commit()
    session.refresh(role)
    return _to_dict(session, role)


# 实现：整体替换角色权限码
def replace_permissions(
    session: Session, *, role_id: uuid.UUID, permission_codes: list[str]
) -> dict:
    role = _require_role(session, role_id)
    _replace_permissions(session, role.id, permission_codes)
    session.commit()
    session.refresh(role)
    return _to_dict(session, role)


# 实现：软删除角色；仍有未删用户绑定时 409
def soft_delete_role(session: Session, *, role_id: uuid.UUID) -> None:
    role = _require_role(session, role_id)
    if _active_user_count(session, role.id) > 0:
        raise ConflictError("仍有用户绑定该角色，无法删除")
    role.is_deleted = True
    session.commit()
