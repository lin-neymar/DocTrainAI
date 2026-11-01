"""数据范围与内容阅读可见性（方案 B）。

- get_accessible_dept_ids：管理范围（data:scope:all → 全公司，否则本部门及下级）
- get_visible_doc_ids / get_visible_course_ids：阅读可见（*:read + audience 子树）
- resolve_audience_dept_ids：写路径解析并校验 audience（B1/B3）

只认 permission 码，禁止用角色 code 判断超管/部门官。
签名 get_accessible_dept_ids / get_visible_doc_ids 固定，阶段 2 检索也必须先调用后者。
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.system.course import Course, CourseAudienceDept
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.services.system import auth_service

_PERM_SCOPE_ALL = "data:scope:all"
_PERM_DEPT_CREATE = "dept:create"
_PERM_DOC_READ = "doc:read"
_PERM_COURSE_READ = "course:read"


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


# 实现：自下而上收集部门自身及全部祖先 id（用于判断「落在某节点子树内」）
def _dept_ancestor_ids_inclusive(
    session: Session, dept_id: uuid.UUID
) -> list[uuid.UUID]:
    """user_dept ∈ subtree(audience) ⇔ audience ∈ 本列表。"""
    rows = session.execute(
        select(Dept.id, Dept.parent_id).where(Dept.is_deleted.is_(False))
    ).all()
    parent_of: dict[uuid.UUID, uuid.UUID | None] = {
        dept_id_: parent_id for dept_id_, parent_id in rows
    }
    if dept_id not in parent_of:
        return []

    chain: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    current: uuid.UUID | None = dept_id
    while current is not None and current not in seen:
        seen.add(current)
        chain.append(current)
        current = parent_of.get(current)
    return chain


# 实现：是否允许客户端自定义 audience（公司级能力代理，不认角色 code）
def can_customize_audience(session: Session, user_id: uuid.UUID) -> bool:
    """有 data:scope:all 或 dept:create → 可多选；否则按部门官规则固定本部门。"""
    permission_codes = auth_service.list_permission_codes_for_user(session, user_id)
    return (
        _PERM_SCOPE_ALL in permission_codes or _PERM_DEPT_CREATE in permission_codes
    )


# 实现：对外提供部门子树 id（含自身），供列表筛选等复用
def get_dept_subtree_ids(session: Session, root_id: uuid.UUID) -> list[uuid.UUID]:
    return _dept_subtree_ids(session, root_id)


# 实现：计算用户可访问的部门 id（全公司或本部门及下级）
def get_accessible_dept_ids(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """返回当前用户管理数据范围内的部门 id 列表（SERVER_SPEC 签名，阶段 2 不改）。

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


# 实现：计算用户可见的文档 id（doc:read + audience 子树；无 scope:all 旁路）
def get_visible_doc_ids(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """返回当前用户可见的未删除文档 id（SERVER_SPEC 签名，阶段 2 不改）。

    判断顺序：
      1. 没有 doc:read → []
      2. 用户所在部门落在该文档任一 audience 节点的子树内 → 可见
      3. 不再因 data:scope:all 自动可见全部文档（B2）
    """
    permission_codes = auth_service.list_permission_codes_for_user(session, user_id)
    if _PERM_DOC_READ not in permission_codes:
        return []

    user = auth_service.get_active_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"user not found or deleted: {user_id}")

    ancestors = _dept_ancestor_ids_inclusive(session, user.dept_id)
    if not ancestors:
        return []

    stmt = (
        select(Doc.id)
        .join(DocAudienceDept, DocAudienceDept.doc_id == Doc.id)
        .where(Doc.is_deleted.is_(False), DocAudienceDept.dept_id.in_(ancestors))
        .distinct()
        .order_by(Doc.id)
    )
    return list(session.scalars(stmt).all())


# 实现：计算用户可见的课程 id（course:read + audience 子树；与文档同构）
def get_visible_course_ids(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """返回当前用户可见的未删除课程 id（需 course:read；无 scope:all 旁路）。"""
    permission_codes = auth_service.list_permission_codes_for_user(session, user_id)
    if _PERM_COURSE_READ not in permission_codes:
        return []

    user = auth_service.get_active_user_by_id(session, user_id)
    if user is None:
        raise ValueError(f"user not found or deleted: {user_id}")

    ancestors = _dept_ancestor_ids_inclusive(session, user.dept_id)
    if not ancestors:
        return []

    stmt = (
        select(Course.id)
        .join(CourseAudienceDept, CourseAudienceDept.course_id == Course.id)
        .where(
            Course.is_deleted.is_(False),
            CourseAudienceDept.dept_id.in_(ancestors),
        )
        .distinct()
        .order_by(Course.id)
    )
    return list(session.scalars(stmt).all())


# 实现：写路径解析 audience（B3 部门官固定本部门；B1 校验子树∩可访问）
def resolve_audience_dept_ids(
    session: Session,
    *,
    operator_id: uuid.UUID,
    owner_dept_id: uuid.UUID,
    audience_dept_ids: list[uuid.UUID] | None,
) -> list[uuid.UUID]:
    """返回最终写入的 audience 部门 id 列表（去重、保序）。

    - 无 data:scope:all 且无 dept:create → 忽略客户端，固定 [操作者 dept_id]（B3）
    - 可自定义且未传 → 默认 [归属 dept_id]
    - 可自定义且传入 → 使用传入列表（不可为空）
    - 每个节点须 ∈ 归属子树 ∩ 操作者可访问部门（B1）；部门无效统一 404
    """
    user = auth_service.get_active_user_by_id(session, operator_id)
    if user is None:
        raise ValueError(f"user not found or deleted: {operator_id}")

    if not can_customize_audience(session, operator_id):
        resolved = [user.dept_id]
    elif audience_dept_ids is None:
        resolved = [owner_dept_id]
    else:
        resolved = list(dict.fromkeys(audience_dept_ids))
        if not resolved:
            raise ValidationFailedError("可见组织不能为空")

    owner_subtree = set(_dept_subtree_ids(session, owner_dept_id))
    accessible = set(get_accessible_dept_ids(session, operator_id))
    for dept_id in resolved:
        dept = session.scalar(
            select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
        )
        if (
            dept is None
            or dept_id not in owner_subtree
            or dept_id not in accessible
        ):
            raise NotFoundError("部门不存在")
    return resolved
