"""部门业务：范围内查询、树、增删改与成环/409 校验。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.system.dept import Dept
from app.models.system.user import User
from app.services.system import auth_service, scope_service
from app.utils.pagination import page_offset

_PERM_SCOPE_ALL = "data:scope:all"


# 实现：把 ORM 部门转成接口用的 dict
def _to_dict(dept: Dept) -> dict:
    return {
        "id": str(dept.id),
        "name": dept.name,
        "parent_id": str(dept.parent_id) if dept.parent_id else None,
        "created_at": dept.created_at.isoformat() if dept.created_at else None,
        "updated_at": dept.updated_at.isoformat() if dept.updated_at else None,
    }


# 实现：取用户可访问部门 id 集合
def _accessible_set(session: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(scope_service.get_accessible_dept_ids(session, user_id))


# 实现：断言部门在用户数据范围内，否则 404
def _require_accessible(
    session: Session, user_id: uuid.UUID, dept_id: uuid.UUID
) -> Dept:
    dept = session.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
    )
    if dept is None or dept_id not in _accessible_set(session, user_id):
        raise NotFoundError("部门不存在")
    return dept


# 实现：判断把 parent 设为目标是否会形成环（不能挂到自己或子孙下）
def _would_create_cycle(
    session: Session, dept_id: uuid.UUID, new_parent_id: uuid.UUID
) -> bool:
    if new_parent_id == dept_id:
        return True
    # 沿 parent 链向上走；若碰到 dept_id，说明 new_parent 在其子树内
    current: uuid.UUID | None = new_parent_id
    seen: set[uuid.UUID] = set()
    while current is not None:
        if current == dept_id:
            return True
        if current in seen:
            break
        seen.add(current)
        parent = session.scalar(
            select(Dept.parent_id).where(Dept.id == current, Dept.is_deleted.is_(False))
        )
        current = parent
    return False


# 实现：分页列出用户可见部门
def list_depts(
    session: Session,
    *,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    accessible = list(_accessible_set(session, user_id))
    if not accessible:
        return [], 0

    total = session.scalar(
        select(func.count())
        .select_from(Dept)
        .where(Dept.is_deleted.is_(False), Dept.id.in_(accessible))
    ) or 0

    rows = session.scalars(
        select(Dept)
        .where(Dept.is_deleted.is_(False), Dept.id.in_(accessible))
        .order_by(Dept.created_at, Dept.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(d) for d in rows], int(total)


# 实现：构建用户可见范围内的部门树
def get_dept_tree(session: Session, user_id: uuid.UUID) -> list[dict]:
    accessible = _accessible_set(session, user_id)
    if not accessible:
        return []

    rows = list(
        session.scalars(
            select(Dept)
            .where(Dept.is_deleted.is_(False), Dept.id.in_(accessible))
            .order_by(Dept.name, Dept.id)
        ).all()
    )
    by_id = {d.id: d for d in rows}
    children_map: dict[uuid.UUID | None, list[Dept]] = {}
    for d in rows:
        # 父不在可见集合内时，当作本范围内的「局部根」
        parent_key = d.parent_id if d.parent_id in by_id else None
        children_map.setdefault(parent_key, []).append(d)

    def build(node: Dept) -> dict:
        kids = children_map.get(node.id, [])
        return {
            "id": str(node.id),
            "name": node.name,
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "children": [build(c) for c in kids],
        }

    roots = children_map.get(None, [])
    return [build(r) for r in roots]


# 实现：部门详情（须在数据范围内）
def get_dept(session: Session, user_id: uuid.UUID, dept_id: uuid.UUID) -> dict:
    dept = _require_accessible(session, user_id, dept_id)
    return _to_dict(dept)


# 实现：创建部门（需调用方已校验 dept:create）
def create_dept(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None,
) -> dict:
    codes = auth_service.list_permission_codes_for_user(session, user_id)
    if parent_id is None:
        if _PERM_SCOPE_ALL not in codes:
            raise ForbiddenError("无权创建根部门")
    else:
        _require_accessible(session, user_id, parent_id)

    dept = Dept(name=name, parent_id=parent_id, is_deleted=False)
    session.add(dept)
    session.commit()
    session.refresh(dept)
    return _to_dict(dept)


# 实现：更新部门名称或父级
def update_dept(
    session: Session,
    *,
    user_id: uuid.UUID,
    dept_id: uuid.UUID,
    name: str | None,
    parent_id: uuid.UUID | None,
    parent_id_provided: bool,
) -> dict:
    dept = _require_accessible(session, user_id, dept_id)
    codes = auth_service.list_permission_codes_for_user(session, user_id)

    if name is not None:
        dept.name = name

    if parent_id_provided:
        if parent_id is None:
            if _PERM_SCOPE_ALL not in codes:
                raise ForbiddenError("无权将部门设为根部门")
            dept.parent_id = None
        else:
            if parent_id == dept_id:
                raise ConflictError("不能将部门的父级设为自己")
            _require_accessible(session, user_id, parent_id)
            if _would_create_cycle(session, dept_id, parent_id):
                raise ConflictError("不能将部门挂到自己的下级之下")
            dept.parent_id = parent_id

    session.commit()
    session.refresh(dept)
    return _to_dict(dept)


# 实现：软删除部门（有子部门或用户时 409）
def soft_delete_dept(
    session: Session, *, user_id: uuid.UUID, dept_id: uuid.UUID
) -> None:
    _require_accessible(session, user_id, dept_id)

    child_count = session.scalar(
        select(func.count())
        .select_from(Dept)
        .where(
            Dept.parent_id == dept_id,
            Dept.is_deleted.is_(False),
        )
    ) or 0
    if child_count > 0:
        raise ConflictError("存在下级部门，无法删除")

    user_count = session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.dept_id == dept_id, User.is_deleted.is_(False))
    ) or 0
    if user_count > 0:
        raise ConflictError("部门下仍有用户，无法删除")

    dept = session.scalar(select(Dept).where(Dept.id == dept_id))
    assert dept is not None
    dept.is_deleted = True
    session.commit()
