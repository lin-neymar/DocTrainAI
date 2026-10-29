"""E：数据范围 service（E-B 部门 + E-C 文档）。

- get_accessible_dept_ids：能碰哪些部门
- get_visible_doc_ids：能当作「存在且可读」的文档 id（详情/下载/阶段 2 检索前过滤）

只认 permission 码，禁止用角色 code 判断超管。
签名固定，阶段 2 检索也必须先调用 get_visible_doc_ids。
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system.dept import Dept
from app.models.system.doc import Doc
from app.services.system import auth_service

_PERM_SCOPE_ALL = "data:scope:all"
_PERM_DOC_READ = "doc:read"


# 实现：收集某部门及其全部下级部门 id
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


# 实现：列出全部未软删部门 id
def _all_active_dept_ids(session: Session) -> list[uuid.UUID]:
    stmt = select(Dept.id).where(Dept.is_deleted.is_(False)).order_by(Dept.id)
    return list(session.scalars(stmt).all())


# 实现：计算用户可访问的部门 id（全公司或本部门及下级）
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


# 实现：计算用户可见的文档 id（需 doc:read，再按数据范围过滤）
def get_visible_doc_ids(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """返回当前用户可见的未删除文档 id（SERVER_SPEC 签名，阶段 2 不改）。

    判断顺序（必须按此顺序，勿打乱）：
      1. 没有 doc:read → []（连列表都不该看到制度文档）
      2. 有 data:scope:all → 全部未删文档
      3. 否则 → doc.dept_id 落在 get_accessible_dept_ids 集合内

    F 阶段：详情/下载时若 doc_id 不在本列表 → 返回 404（不泄露「是否存在」）。
    """
    permission_codes = auth_service.list_permission_codes_for_user(session, user_id)
    if _PERM_DOC_READ not in permission_codes:
        return []

    if _PERM_SCOPE_ALL in permission_codes:
        stmt = select(Doc.id).where(Doc.is_deleted.is_(False)).order_by(Doc.id)
        return list(session.scalars(stmt).all())

    accessible_dept_ids = get_accessible_dept_ids(session, user_id)
    if not accessible_dept_ids:
        return []

    stmt = (
        select(Doc.id)
        .where(Doc.is_deleted.is_(False), Doc.dept_id.in_(accessible_dept_ids))
        .order_by(Doc.id)
    )
    return list(session.scalars(stmt).all())
