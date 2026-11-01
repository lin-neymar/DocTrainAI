"""文档 API 的入参 Schema。

创建走 multipart（title + dept_id + file + 可选 audience_dept_ids JSON）；
更新走 JSON DocUpdate。
"""

from uuid import UUID

from pydantic import BaseModel, Field


class DocUpdate(BaseModel):
    """仅改元数据与可见组织；不换原文件（阶段 1 不提供覆盖上传）。"""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    dept_id: UUID | None = None
    # 未出现在请求体 → 不改 audience（部门官仍由服务端 B3 强制）
    audience_dept_ids: list[UUID] | None = None


class DocBatchDelete(BaseModel):
    """批量软删除：ids 去重后处理，上限 100；越管理范围整批失败。"""

    ids: list[UUID] = Field(min_length=1, max_length=100)
