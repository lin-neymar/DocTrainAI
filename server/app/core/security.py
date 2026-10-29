"""D-A：密码校验与 Access Token（JWT）工具层。

HTTP 路由在 D-B（app/api/system/auth.py）；本文件只做密码与 JWT 工具。职责：
  1. 登录时：比对用户输入的明文与库里的 bcrypt hash（verify_password）
  2. 登录成功：签发 JWT（create_access_token）；请求进来：解析 JWT（decode_access_token）

阶段 1 约定（SERVER_SPEC / WEB_SPEC）：
  - 只有 Access Token，没有 Refresh Token
  - 前端把 token 放 localStorage，刷新页面后调 /me（D-B 实现）
  - 密钥与过期分钟数只来自环境变量，见 app.config.settings
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings
from app.core.exceptions import UnauthorizedError

# 对称密钥算法：服务端用 JWT_SECRET 签名与验签（阶段 1 够用，勿把 secret 提交 Git）
_ALGORITHM = "HS256"


# 实现：明文密码 → bcrypt 哈希（创建用户 / 重置密码用）
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# 实现：校验明文密码是否匹配 bcrypt 哈希
def verify_password(plain: str, password_hash: str) -> bool:
    """验证明文密码是否与数据库存储的 bcrypt hash 匹配。

    seed 写入 hash 的方式与这里读取方式一致（都是 bcrypt 库）。
    登录失败时 service 层返回 None，由路由统一抛 401，不在此处区分「用户不存在」和「密码错」。
    """
    return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))


# 实现：为用户签发 Access Token（JWT）
def create_access_token(*, user_id: uuid.UUID) -> str:
    """签发 JWT 字符串，payload 最小化：只放 sub（用户 id）与 exp（过期时间）。

    sub 用 str(user_id)，因为 JWT 标准里 claim 常用字符串；解码后再转回 UUID。
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


# 实现：解析并校验 JWT，返回 user_id（失败抛 401）
def decode_access_token(token: str) -> uuid.UUID:
    """校验签名与 exp，成功则返回 user_id。

    任意失败（篡改、过期、缺 sub）→ UnauthorizedError → 全局 handler 转成 401 / 40100。
    D-B 的 get_current_user 会调用此函数，再按 id 查库确认用户未软删。
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("invalid or expired token") from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise UnauthorizedError("invalid or expired token")

    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise UnauthorizedError("invalid or expired token") from exc
