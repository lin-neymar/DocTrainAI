"""D-B：认证 HTTP 接口（薄路由：校验入参 → 调 service → success 包装）。

- POST /auth/login     无需 Token
- GET  /auth/me        需要 Bearer（Depends get_current_user）
- POST /auth/logout    需要 Bearer；JWT 无状态，服务端只返回成功
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.response import success
from app.core.security import create_access_token
from app.database import get_db
from app.models.system.user import User
from app.schemas.system.auth import LoginRequest, LoginResponseData, MeDept, MeResponseData, MeUser
from app.services.system import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    summary="登录",
    description="校验用户名与密码，签发 Access Token。无 Refresh Token。",
)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> dict:
    user = auth_service.authenticate_user(db, body.username, body.password)
    if user is None:
        raise UnauthorizedError("invalid username or password")

    token = create_access_token(user_id=user.id)
    return success(LoginResponseData(access_token=token).model_dump())


@router.post(
    "/logout",
    summary="退出登录",
    description="无状态 JWT：服务端不维护会话表；前端删除 localStorage 中的 token 即可。",
)
def logout(_current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    return success()


@router.get(
    "/me",
    summary="当前用户",
    description="刷新页面后带 token 调用，恢复 Pinia 中的用户信息与 permission_codes。",
)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    dept = auth_service.get_dept_by_id(db, current_user.dept_id)
    if dept is None:
        raise UnauthorizedError()

    data = MeResponseData(
        user=MeUser(id=str(current_user.id), username=current_user.username),
        dept=MeDept(id=str(dept.id), name=dept.name),
        role_names=auth_service.list_role_names_for_user(db, current_user.id),
        permission_codes=auth_service.list_permission_codes_for_user(db, current_user.id),
    )
    return success(data.model_dump())
