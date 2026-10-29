"""认证接口 Schema（Create / Response 与 SERVER_SPEC、WEB_SPEC 对齐）。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class LoginResponseData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeUser(BaseModel):
    id: str
    username: str


class MeDept(BaseModel):
    id: str
    name: str


class MeResponseData(BaseModel):
    user: MeUser
    dept: MeDept
    role_names: list[str]
    permission_codes: list[str]
