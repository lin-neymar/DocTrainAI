"""E：数据范围 service（E-B 部门；E-C 文档见后续函数）。

get_accessible_dept_ids：用户管理、部门树、重置密码等「能碰哪些部门」。
只认 permission 码 data:scope:all，禁止用角色 code 判断超管。
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system.dept import Dept
from app.services.system import auth_service

_PERM_SCOPE_ALL = "data:scope:all"


def _dept_subtree_ids(session: Session, root_id: uuid.UUID) -> list[uuid.UUID]:
    """从 root_id 起：自身 + 所有未删除下级（栈遍历，阶段 1 树规模足够）。"""
    rows = session.execute(
        select(Dept.id, Dept.parent_id).where(Dept.is_deleted.is_(False))
    ).all()
    children: dict[uuid.UUID | None, list[uuid.UUID]] = defaultdict(list)
    for dept_id, parent_id in rows:
        children[parent_id].append(dept_id)

    collected: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        collected.append(current)
        stack.extend(children.get(current, []))
    return collected


def _all_active_dept_ids(session: Session) -> list[uuid.UUID]:
    stmt = select(Dept.id).where(Dept.is_deleted.is_(False)).order_by(Dept.id)
    return list(session.scalars(stmt).all())


def get_accessible_dept_ids(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """返回当前用户数据范围内的部门 id 列表（SERVER_SPEC 签名，阶段 2 不改）。

    - 拥有 data:scope:all → 全部未删部门
    - 否则 → user.dept_id 所在节点 + 其下全部子部门（不含兄弟分支）
    """
    user = auth_service.get_active_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"user not found or deleted: {user_id}")

    permission_codes = auth_service.list_permission_codes_for_user(session, user_id)
    if _PERM_SCOPE_ALL in permission_codes:
        return _all_active_dept_ids(session)
    return _dept_subtree_ids(session, user.dept_id)
