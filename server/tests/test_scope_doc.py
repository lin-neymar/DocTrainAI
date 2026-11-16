"""E-C / S5：get_visible_doc_ids 与 audience 写路径（需 Postgres + seed）。"""

import uuid

import bcrypt
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.user import User, UserRole
from app.services.system import scope_service
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_doc(
    session,
    *,
    title: str,
    dept_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    audience_dept_ids: list[uuid.UUID] | None = None,
) -> Doc:
    doc = Doc(
        title=title,
        dept_id=dept_id,
        original_filename=f"{title}.pdf",
        extension="pdf",
        size_bytes=100,
        storage_key=f"test/{uuid.uuid4()}.pdf",
        sha256="b" * 64,
        uploaded_by=uploaded_by,
        is_deleted=False,
    )
    session.add(doc)
    session.flush()
    for aid in audience_dept_ids if audience_dept_ids is not None else [dept_id]:
        session.add(DocAudienceDept(doc_id=doc.id, dept_id=aid))
    return doc


@pytest.fixture
def seeded_session():
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
            yield session
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")


def test_admin_sees_all_docs_with_read_all(seeded_session) -> None:
    """超管在根：有 data:read:all → 不依赖 audience 覆盖，全部文档可见。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None

    child = Dept(name=f"E-C子-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    session.add(child)
    session.flush()

    # audience=root → 根上超管可见
    d_root_aud = _create_doc(
        session,
        title="ec-root-aud",
        dept_id=child.id,
        uploaded_by=admin.id,
        audience_dept_ids=[root.id],
    )
    # audience 仅 child → 超管凭 data:read:all 仍可见
    d_child_only = _create_doc(
        session,
        title="ec-child-only",
        dept_id=child.id,
        uploaded_by=admin.id,
        audience_dept_ids=[child.id],
    )
    session.commit()

    visible = set(scope_service.get_visible_doc_ids(session, admin.id))
    assert d_root_aud.id in visible
    assert d_child_only.id in visible


def test_staff_sees_docs_in_audience_subtree(seeded_session) -> None:
    """staff：落在 audience 节点子树内可读；兄弟分支不可读。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert admin is not None and staff_role is not None

    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    branch_a = Dept(name=f"E-CA-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    branch_b = Dept(name=f"E-CB-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    session.add_all([branch_a, branch_b])
    session.flush()
    child_a = Dept(
        name=f"E-CAsub-{uuid.uuid4().hex[:6]}", parent_id=branch_a.id, is_deleted=False
    )
    session.add(child_a)
    session.flush()

    staff = User(
        username=f"staff_ec_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=child_a.id,
        is_deleted=False,
    )
    session.add(staff)
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))

    # audience=branch_a → 子树内 staff 可见
    doc_a = _create_doc(
        session,
        title="in-a",
        dept_id=branch_a.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_a.id],
    )
    doc_b = _create_doc(
        session,
        title="in-b",
        dept_id=branch_b.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_b.id],
    )
    session.commit()

    visible = set(scope_service.get_visible_doc_ids(session, staff.id))
    assert doc_a.id in visible
    assert doc_b.id not in visible


def test_scope_all_without_read_all_does_not_reveal_doc(seeded_session) -> None:
    """仅 data:scope:all + doc:read（无 data:read:all）→ 仍不可旁路阅读（B2）。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    leaf = Dept(name=f"E-Cleaf-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    session.add(leaf)
    session.flush()

    doc = _create_doc(
        session,
        title="scope-bypass-check",
        dept_id=leaf.id,
        uploaded_by=admin.id,
        audience_dept_ids=[leaf.id],
    )

    # 自定义角色：doc:read + data:scope:all，但不含 data:read:all
    role = Role(
        code=f"scope_only_{uuid.uuid4().hex[:8]}", name="范围角色", is_deleted=False
    )
    session.add(role)
    session.flush()
    for code in ("doc:read", "data:scope:all"):
        perm = session.scalar(
            select(Permission).where(
                Permission.code == code, Permission.is_deleted.is_(False)
            )
        )
        assert perm is not None
        session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    user = User(
        username=f"scopeonly_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=root.id,
        is_deleted=False,
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()

    visible = set(scope_service.get_visible_doc_ids(session, user.id))
    assert doc.id not in visible

    # 超管有 data:read:all → 旁路可见
    admin_visible = set(scope_service.get_visible_doc_ids(session, admin.id))
    assert doc.id in admin_visible


def test_user_without_doc_read_sees_no_docs(seeded_session) -> None:
    """无任何角色 → 无 doc:read → 可见文档恒为空。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None

    _create_doc(session, title="hidden", dept_id=root.id, uploaded_by=admin.id)

    bare = User(
        username=f"noperm_ec_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=root.id,
        is_deleted=False,
    )
    session.add(bare)
    session.commit()

    assert scope_service.get_visible_doc_ids(session, bare.id) == []


def test_dept_publisher_audience_forced_to_own_dept(seeded_session) -> None:
    """无 scope:all 且无 dept:create（部门官特征）→ audience 固定为本部门，忽略客户端。"""
    session = seeded_session
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    branch = Dept(name=f"E-Cda-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    session.add(branch)
    session.flush()

    dept_admin_role = session.scalar(
        select(Role).where(Role.code == "dept_admin", Role.is_deleted.is_(False))
    )
    assert dept_admin_role is not None
    user = User(
        username=f"da_ec_{uuid.uuid4().hex[:8]}",
        password_hash=_hash_password("pass"),
        dept_id=branch.id,
        is_deleted=False,
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=dept_admin_role.id))
    session.commit()

    assert not scope_service.can_customize_audience(session, user.id)

    # 客户端企图把 audience 设为根 → 被忽略，写成操作者本部门
    resolved = scope_service.resolve_audience_dept_ids(
        session,
        operator_id=user.id,
        owner_dept_id=branch.id,
        audience_dept_ids=[root.id],
    )
    assert resolved == [branch.id]


def test_audience_must_be_in_owner_subtree(seeded_session) -> None:
    """B1：可自定义时，audience 落在归属子树外 → 404。"""
    session = seeded_session
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    assert root is not None
    a = Dept(name=f"E-Cb1a-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    b = Dept(name=f"E-Cb1b-{uuid.uuid4().hex[:6]}", parent_id=root.id, is_deleted=False)
    session.add_all([a, b])
    session.flush()
    session.commit()

    from app.core.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        scope_service.resolve_audience_dept_ids(
            session,
            operator_id=admin.id,
            owner_dept_id=a.id,
            audience_dept_ids=[b.id],
        )
