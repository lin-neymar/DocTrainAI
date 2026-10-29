"""角色 / 权限 API 的入参 Schema。

权限码从 DB 读取，不在此写死清单；业务分支只认 permission code，不认 role.code。
"""

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class RoleUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)


class RolePermissionsUpdate(BaseModel):
    """整体替换角色权限；未知 code 由 service 返回 404。"""

    permission_codes: list[str] = Field(default_factory=list)
