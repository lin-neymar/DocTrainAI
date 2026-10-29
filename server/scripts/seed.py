"""C3：幂等种子脚本——把 seed_data 清单写入 PostgreSQL。

用法（在 server/ 目录，且已 docker compose up + alembic upgrade head）：

    .venv/bin/python -m scripts.seed

依赖仓库根目录 .env：
  DATABASE_URL、INIT_ADMIN_USERNAME、INIT_ADMIN_PASSWORD

安全：stdout 不输出明文密码；密码只经 bcrypt 写入 user.password_hash。

幂等：同一库多次执行不会重复插多份根部门/权限/角色；管理员密码会随 .env 更新而重算 hash。
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
from app.models.system.user import User, UserRole
from scripts.seed_data import BUILTIN_ROLE_CODES, PERMISSIONS, ROLES, ROOT_DEPT_NAME


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
        # 允许把展示名改回 seed 约定，不新建第二棵根
        if root.name != ROOT_DEPT_NAME:
            root.name = ROOT_DEPT_NAME
        return root

    root = Dept(name=ROOT_DEPT_NAME, parent_id=None, is_deleted=False)
    session.add(root)
    session.flush()  # 拿到 root.id，供后续 user.dept_id 使用
    return root


# 实现：幂等写入阶段 1 权限码
def ensure_permissions(session: Session) -> dict[str, Permission]:
    """按 code  upsert 权限行；返回 code → ORM，供 sync_role_permissions 用。"""
    by_code: dict[str, Permission] = {}
    for code, name in PERMISSIONS:
        perm = session.scalar(
            select(Permission).where(
                Permission.code == code,
                Permission.is_deleted.is_(False),
            )
        )
        if perm is None:
            perm = Permission(code=code, name=name, is_deleted=False)
            session.add(perm)
            session.flush()
        elif perm.name != name:
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
    """内置角色：删掉该 role 的全部 role_permission 再插入，与 seed_data 表完全一致。

    这样规约变更后重跑 seed 即可对齐，无需手写 SQL 改关联。
    以后若有「非内置、管理员自建角色」，不要放进 BUILTIN_ROLE_CODES，避免被清空权限。
    """
    for code, _name, perm_codes in ROLES:
        if code not in BUILTIN_ROLE_CODES:
            continue
        role = roles_by_code[code]
        session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for perm_code in perm_codes:
            perm = perms_by_code[perm_code]
            session.add(RolePermission(role_id=role.id, permission_id=perm.id))


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
        # 已存在：同步密码与部门（本地改 .env 后重跑 seed 即可改密，阶段 D 登录用）
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
    perms = ensure_permissions(session)
    roles = ensure_roles(session)
    sync_role_permissions(session, roles, perms)
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
        "seed 完成：根部门、9 个权限码、3 个内置角色、"
        f"初始管理员「{settings.init_admin_username}」（密码未输出）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
