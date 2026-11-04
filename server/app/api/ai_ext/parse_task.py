"""解析任务 HTTP：入队与查询。权限复用 doc:read，不新增权限码。"""

from __future__ import annotations  # 开启延迟类型注解，支持模型互相引用

from typing import Annotated  # 类型注解增强，配合Depends使用
from uuid import UUID  # UUID类型

from fastapi import APIRouter, Depends  # 路由对象、依赖注入
from sqlalchemy.orm import Session  # 数据库会话

from app.core.deps import require_permission  # 权限校验依赖
from app.core.response import success  # 统一成功返回包装器
from app.database import get_db  # 获取数据库会话依赖
from app.models.system.user import User  # 用户ORM模型
from app.schemas.ai_ext.parse_task import ParseTaskCreate, ParseTaskOut  # 任务入参、出参Schema
from app.services.ai_ext import parse_task_service  # 解析任务业务服务

# 路由实例，前缀 /parse-tasks，接口分组标签 parse-tasks
router = APIRouter(prefix="/parse-tasks", tags=["parse-tasks"])

@router.post(
    "",
    summary="创建解析任务并入队",
    description="对可见文档入队异步解析。需要 doc:read。S3 仅状态机占位。",
)
# 创建解析任务并入队
def create_parse_task(
    body: ParseTaskCreate,  # 请求体：待解析文档ID
    current_user: Annotated[
        User, Depends(require_permission("doc:read"))
    ], # 当前用户，校验doc:read权限
    db: Annotated[Session, Depends(get_db)], # 数据库会话
) -> dict:
    # 调用业务服务，创建任务并推入ARQ队列
    task = parse_task_service.create_and_enqueue(
        db,user_id=current_user.id,doc_id=body.doc_id,
    )
    # ORM对象转为响应Schema，序列化后包装统一成功返回
    return success(ParseTaskOut.model_validate(task).model_dump(mode="json"))

@router.get(
    "/{task_id}",
    summary="查询解析任务",
    description="任务所属文档须对当前用户可见。需要 doc:read。",
)
def get_parse_task(
    task_id: UUID,
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    task = parse_task_service.get_task_for_user(
        db, user_id=current_user.id, task_id=task_id
    )
    return success(ParseTaskOut.model_validate(task).model_dump(mode="json"))

@router.get(
    "/by-doc/{doc_id}/latest",
    summary="某文档最新解析任务",
    description="无任务时 data 为 null。需要 doc:read。",
)
def get_latest_parse_task(
    doc_id: UUID,
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    task = parse_task_service.get_latest_for_doc(
        db, user_id=current_user.id, doc_id=doc_id
    )
    if task is None:
        return success(None)
    return success(ParseTaskOut.model_validate(task).model_dump(mode="json"))