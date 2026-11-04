"""ai_ext 与底座事件的装配：上传文档后自动创建解析任务。

架构契约：system 禁止导入 ai_ext。因此底座只暴露回调注册点
（doc_service.register_doc_created_hook），本模块在应用启动时
把 ai_ext 的行为挂上去——依赖方向保持 system 不依赖 ai_ext。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.system.doc import Doc
from app.services.ai_ext import parse_task_service
from app.services.system.doc_service import register_doc_created_hook

logger = logging.getLogger(__name__)

# 实现：文档创建回调——自动创建解析任务并入队
def _on_doc_created(session: Session, doc: Doc) -> None:
    # 入队失败时任务已被标记 failed 并抛出；底座 _notify 会吞掉异常，上传不受影响
    parse_task_service.enqueue_for_doc(session, doc_id=doc.id)


# 实现：注册 ai_ext 的全部底座事件回调；在 main.py 应用启动时调用一次
def register_ai_ext_hooks() -> None:
    register_doc_created_hook(_on_doc_created)
    logger.info("ai_ext hooks registered")