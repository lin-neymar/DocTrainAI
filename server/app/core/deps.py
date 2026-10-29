"""D-B：FastAPI 依赖注入——从请求头解析当前登录用户。

用法（后续业务路由）：
    current_user: Annotated[User, Depends(get_current_user)]

流程：Authorization: Bearer <token> → decode_access_token → 按 id 查未删除用户。
无头、非 Bearer、token 无效、用户已软删 → UnauthorizedError（40100）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.database import get_db
from app.models.system.user import User
from app.services.system import auth_service

# auto_error=False：没有 Authorization 时不走 FastAPI 默认 403，统一抛我们的 40100
_bearer = HTTPBearer(auto_error=False)


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
