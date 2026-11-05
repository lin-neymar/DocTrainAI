"""检索出入参。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field  # Pydantic基础模型、字段描述/校验


# 检索请求体Schema
class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)  # 检索问题文本
    top_k: int = Field(default=5, ge=1, le=50)        # 返回条数上限

# 单条命中结果Schema
class RetrievalItem(BaseModel):
    chunk_id: UUID            # 分片主键
    doc_id: UUID              # 所属文档
    doc_title: str            # 文档标题（引用展示用）
    chunk_index: int          # 文档内顺序
    content: str              # 命中正文
    location: dict | None = None  # 位置元信息（页码/sheet/幻灯片）
    score: float              # 加权合并后的最终得分

# 检索响应Schema
class RetrievalOut(BaseModel):
    items: list[RetrievalItem]  # 得分降序的命中列表