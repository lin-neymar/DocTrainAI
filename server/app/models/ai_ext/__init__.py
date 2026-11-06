"""AI 扩展表 ORM（阶段 2+）。

解析任务、分片、会话等放这里；system 禁止 import 本包。
Alembic 需 import 本包，模型才会进入 Base.metadata。
"""

from app.models.ai_ext.chat import ChatCallLog, ChatMessage, ChatSession
from app.models.ai_ext.chunk import DocChunk
from app.models.ai_ext.parse_task import DocParseTask

__all__ = [
    "ChatCallLog",
    "ChatMessage",
    "ChatSession",
    "DocChunk",
    "DocParseTask",
]