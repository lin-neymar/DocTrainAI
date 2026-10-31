"""幂等种子脚本——把 seed_data 清单写入 PostgreSQL。

用法（在 server/ 目录，且已 docker compose up + alembic upgrade head）：

    .venv/bin/python -m scripts.seed

依赖仓库根目录 .env：
  DATABASE_URL、INIT_ADMIN_USERNAME、INIT_ADMIN_PASSWORD

安全：stdout 不输出明文密码；密码只经 bcrypt 写入 user.password_hash。

幂等：同一库多次执行不会重复插多份根部门/权限/角色/品牌；管理员密码会随 .env 更新而重算 hash。
"""

from __future__ import annotations

import sys

import bcrypt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.system.dept import Dept
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.system_brand import SystemBrand
from app.models.system.user import User, UserRole
from scripts.seed_data import (
    ACTIVE_PERMISSION_COUNT,
    BUILTIN_ROLE_CODES,
    BUILTIN_ROLE_COUNT,
    DEFAULT_BRAND_LOGIN_SUBTITLE,
    DEFAULT_BRAND_SITE_NAME,
    DEPRECATED_PERMISSION_CODES,
    PERMISSIONS,
    ROLES,
    ROOT_DEPT_NAME,
)


# 实现：明文密码 → bcrypt 哈希
def _hash_password(plain: str) -> str:
    """bcrypt 每次 salt 不同，同一明文多次 hash 结果也不同（重跑 seed 会更新 hash 列）。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# 实现：幂等确保根部门存在
def ensure_root_dept(session: Session) -> Dept:
    """保证存在且仅复用「未删除的根部门」（parent_id IS NULL）。"""
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    if root is not None:
        if root.name != ROOT_DEPT_NAME:
            root.name = ROOT_DEPT_NAME
        return root

    root = Dept(name=ROOT_DEPT_NAME, parent_id=None, is_deleted=False)
    session.add(root)
    session.flush()
    return root


# 实现：将旧聚合权限码软删除（停止使用，不物理删行）
def deprecate_old_permissions(session: Session) -> None:
    """把 DEPRECATED 中仍活跃的权限行标为 is_deleted，并清掉其 role_permission。"""
    rows = session.scalars(
        select(Permission).where(
            Permission.code.in_(DEPRECATED_PERMISSION_CODES),
            Permission.is_deleted.is_(False),
        )
    ).all()
    for perm in rows:
        session.execute(
            delete(RolePermission).where(RolePermission.permission_id == perm.id)
        )
        perm.is_deleted = True


# 实现：幂等写入阶段 1 现行权限码
def ensure_permissions(session: Session) -> dict[str, Permission]:
    """按 code upsert 未删除权限行；返回 code → ORM，供 sync_role_permissions 用。"""
    by_code: dict[str, Permission] = {}
    for code, name in PERMISSIONS:
        # 若历史上被误软删，允许复活（同一 code 未删除唯一）
        perm = session.scalar(select(Permission).where(Permission.code == code))
        if perm is None:
            perm = Permission(code=code, name=name, is_deleted=False)
            session.add(perm)
            session.flush()
        else:
            perm.is_deleted = False
            if perm.name != name:
                perm.name = name
        by_code[code] = perm
    return by_code


# 实现：幂等写入内置角色
def ensure_roles(session: Session) -> dict[str, Role]:
    """按 code upsert 角色行；返回 code → ORM。"""
    by_code: dict[str, Role] = {}
    for code, name, _perm_codes in ROLES:
        role = session.scalar(
            select(Role).where(Role.code == code, Role.is_deleted.is_(False))
        )
        if role is None:
            role = Role(code=code, name=name, is_deleted=False)
            session.add(role)
            session.flush()
        elif role.name != name:
            role.name = name
        by_code[code] = role
    return by_code


# 实现：按 seed_data 同步内置角色的权限关联
def sync_role_permissions(
    session: Session,
    roles_by_code: dict[str, Role],
    perms_by_code: dict[str, Permission],
) -> None:
    """内置角色：删掉该 role 的全部 role_permission 再插入，与 seed_data 表完全一致。"""
    for code, _name, perm_codes in ROLES:
        if code not in BUILTIN_ROLE_CODES:
            continue
        role = roles_by_code[code]
        session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for perm_code in perm_codes:
            perm = perms_by_code[perm_code]
            session.add(RolePermission(role_id=role.id, permission_id=perm.id))


# 实现：幂等确保全局品牌一行（T2/T3 默认；Logo 可空）
def ensure_system_brand(session: Session) -> SystemBrand:
    """库中只保留一行品牌；已存在则把空缺的默认文案补齐，不强制覆盖管理员已改文案。"""
    brand = session.scalar(select(SystemBrand).limit(1))
    if brand is None:
        brand = SystemBrand(
            site_name=DEFAULT_BRAND_SITE_NAME,
            login_subtitle=DEFAULT_BRAND_LOGIN_SUBTITLE,
            logo_storage_key=None,
        )
        session.add(brand)
        session.flush()
        return brand
    # 已有行：仅在异常空串时回填默认，避免每次 seed 冲掉超管修改
    if not (brand.site_name or "").strip():
        brand.site_name = DEFAULT_BRAND_SITE_NAME
    if not (brand.login_subtitle or "").strip():
        brand.login_subtitle = DEFAULT_BRAND_LOGIN_SUBTITLE
    return brand


# 实现：幂等创建/更新初始超级管理员
def ensure_init_admin(session: Session, root_dept: Dept, roles_by_code: dict[str, Role]) -> User:
    """创建或更新 .env 指定的初始管理员：归属根部门，角色 super_admin。"""
    username = settings.init_admin_username.strip()
    password = settings.init_admin_password
    if not username or not password:
        raise ValueError("INIT_ADMIN_USERNAME 与 INIT_ADMIN_PASSWORD 不能为空")

    password_hash = _hash_password(password)
    user = session.scalar(
        select(User).where(User.username == username, User.is_deleted.is_(False))
    )
    if user is None:
        user = User(
            username=username,
            password_hash=password_hash,
            dept_id=root_dept.id,
            is_deleted=False,
        )
        session.add(user)
        session.flush()
    else:
        user.password_hash = password_hash
        user.dept_id = root_dept.id

    super_admin = roles_by_code["super_admin"]
    link = session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == super_admin.id,
        )
    )
    if link is None:
        session.add(UserRole(user_id=user.id, role_id=super_admin.id))

    return user


# 实现：按固定顺序执行完整种子写入
def run_seed(session: Session) -> None:
    """单事务内的写入顺序：外键依赖从前到后，不要打乱。"""
    root = ensure_root_dept(session)
    deprecate_old_permissions(session)
    perms = ensure_permissions(session)
    roles = ensure_roles(session)
    sync_role_permissions(session, roles, perms)
    ensure_system_brand(session)
    ensure_init_admin(session, root, roles)


# 实现：命令行入口，跑 seed 并提交事务
def main() -> int:
    try:
        with SessionLocal() as session:
            run_seed(session)
            session.commit()
    except Exception as exc:
        print(f"seed 失败: {exc}", file=sys.stderr)
        return 1

    print(
        f"seed 完成：根部门、{ACTIVE_PERMISSION_COUNT} 个现行权限码、"
        f"{BUILTIN_ROLE_COUNT} 个内置角色、默认品牌、"
        f"初始管理员「{settings.init_admin_username}」（密码未输出）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
