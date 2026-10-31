"""课程 API 的入参 Schema。"""

from uuid import UUID

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    dept_id: UUID
    audience_dept_ids: list[UUID] | None = None


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    dept_id: UUID | None = None
    audience_dept_ids: list[UUID] | None = None


class CourseDocsUpdate(BaseModel):
    """整体替换课程挂接的文档；文档须在操作者可见范围内。"""

    doc_ids: list[UUID] = Field(default_factory=list)
