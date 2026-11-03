"""解析任务出入参。"""

from datetime import datetime  # 日期时间类型
from uuid import UUID          # UUID类型注解

from pydantic import BaseModel  # Pydantic基础模型、字段描述/校验

# 创建解析任务请求体Schema
class ParseTaskCreate(BaseModel):
    doc_id: UUID  # 待解析文档ID

# 解析任务返回响应Schema
class ParseTaskOut(BaseModel):
    id: UUID                  # 任务主键ID
    doc_id: UUID              # 关联文档ID
    status: str               # 任务状态
    error_summary: str | None = None  # 失败时错误摘要，可为空
    created_at: datetime      # 创建时间
    updated_at: datetime      # 更新时间

    model_config = {
        "from_attributes": True,  # 支持从ORM模型自动读取属性转Pydantic对象
    }