"""用户 API 的入参/出参 Schema（永不包含 password_hash）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    dept_id: UUID
    role_ids: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    dept_id: UUID | None = None
    role_ids: list[UUID] | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class UserBatchDelete(BaseModel):
    """批量软删除：ids 去重后处理，上限与列表 page_size 对齐。"""

    ids: list[UUID] = Field(min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: UUID
    username: str
    dept_id: UUID
    role_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
