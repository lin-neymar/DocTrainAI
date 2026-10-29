"""文档 API 的入参 Schema。

创建走 multipart（title + dept_id + file），不在此用 JSON Create。
"""

from uuid import UUID

from pydantic import BaseModel, Field


class DocUpdate(BaseModel):
    """仅改元数据；不换原文件（阶段 1 不提供覆盖上传）。"""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    dept_id: UUID | None = None
