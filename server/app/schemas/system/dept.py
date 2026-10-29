"""部门 API 的入参/出参 Schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    # None 表示创建根部门（仅持有 data:scope:all 时允许）
    parent_id: UUID | None = None


class DeptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    parent_id: UUID | None = None


class DeptResponse(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeptTreeNode(BaseModel):
    """部门树节点（children 递归）。"""

    id: UUID
    name: str
    parent_id: UUID | None
    children: list["DeptTreeNode"] = Field(default_factory=list)
