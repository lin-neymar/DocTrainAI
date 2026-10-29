"""D-A：security 模块单元测试（不连 PostgreSQL，不启动 HTTP）。"""

import uuid

import bcrypt
import jwt
import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, decode_access_token, verify_password


def test_verify_password_roundtrip() -> None:
    hashed = bcrypt.hashpw(b"secret-pass", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("secret-pass", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id)
    assert decode_access_token(token) == user_id


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(user_id=uuid.uuid4())
    parts = token.split(".")
    bogus = ".".join([parts[0], parts[1], "invalidsignature"])
    with pytest.raises(UnauthorizedError):
        decode_access_token(bogus)


def test_decode_rejects_wrong_secret() -> None:
    """用另一把密钥签名的 token，应用 JWT_SECRET 验签时必须失败。"""
    user_id = uuid.uuid4()
    token = jwt.encode(
        {"sub": str(user_id)},
        "another-secret",
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(token)
