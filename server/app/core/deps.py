"""鉴权依赖（D-B + E-A）。

get_current_user：证明「已登录是谁」→ 401
require_permission：在已登录前提下证明「有没有某个权限码」→ 403

业务路由典型写法（F 阶段）：
    user: Annotated[User, Depends(require_permission("dept:manage"))]

注意：require_permission 只管功能权限，不代替数据范围（E-B/E-C 的 dept/doc 范围函数）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.database import get_db
from app.models.system.user import User
from app.services.system import auth_service

# auto_error=False：没有 Authorization 时不走 FastAPI 默认 403，统一抛我们的 40100
_bearer = HTTPBearer(auto_error=False)


# 实现：从 Bearer Token 解析当前登录用户（失败 → 401）
def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()

    user_id = decode_access_token(credentials.credentials)
    user = auth_service.get_active_user_by_id(db, user_id)
    if user is None:
        # token 仍有效但用户被软删或不存在 → 同样 401，避免泄露状态
        raise UnauthorizedError()
    return user


# 实现：功能权限依赖工厂（缺权限码 → 403）
def require_permission(perm_code: str):
    """E-A：功能权限依赖工厂（返回一个可被 Depends 使用的依赖函数）。

    执行顺序（FastAPI 自动保证）：
      1. 先走 get_current_user → 未登录直接 401，不会走到权限判断
      2. 再从 DB 聚合该用户全部 permission_codes（多角色取并集）
      3. perm_code 不在集合中 → ForbiddenError（40300）

    perm_code 必须与 seed/permission 表里的 code 完全一致，例如 "dept:manage"。
    禁止在这里判断角色名或 role.code（规约：全量范围只看 data:scope:all 码，不看 super_admin）。
    """

    # 实现：校验当前用户是否持有外层指定的权限码
    def _require(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        codes = auth_service.list_permission_codes_for_user(db, current_user.id)
        if perm_code not in codes:
            raise ForbiddenError()
        return current_user

    return _require
