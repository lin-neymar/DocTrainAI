"""对话模型客户端（OpenAI 兼容；与 Embedding 配置分开）。"""

from __future__ import annotations

from typing import Callable

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.config import settings

# 意图三类（业务代码只认这三个字符串）
INTENT_RETRIEVAL = "retrieval"
INTENT_CHIT_CHAT = "chit_chat"
INTENT_REFUSE = "refuse"

# 意图分类提示词：只输出一个词
_INTENT_PROMPT = (
    "判断用户问题属于哪一类，只输出一个词，不要输出任何其他内容："
    "retrieval（与公司规章制度或工作资料相关，需要检索文档回答）、"
    "chit_chat（与资料无关的日常闲聊或常识问题，如问候、天气、"
    "『广州在哪个省』等通用知识）、"
    "refuse（违法、有害等应拒答的问题）。"
)


# 实现：获取对话模型实例（兼容 DashScope 等 OpenAI 兼容接口）
def get_chat_model() -> ChatOpenAI:
    if not settings.chat_base_url or not settings.chat_api_key:
        raise RuntimeError("未配置 CHAT_BASE_URL 或 CHAT_API_KEY")
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.chat_api_key,
        base_url=settings.chat_base_url.rstrip("/"),
        temperature=0.2,
        timeout=60,
    )


# 实现：意图分类——一次模型调用；非法输出兜底 retrieval（有拒答阈值兜底，最安全）
def classify_intent(question: str) -> str:
    raw = get_chat_model().invoke(
        [("system", _INTENT_PROMPT), ("human", question)]
    ).content
    word = str(raw).strip().lower()
    for intent in (INTENT_RETRIEVAL, INTENT_CHIT_CHAT, INTENT_REFUSE):
        if intent in word:
            return intent
    return INTENT_RETRIEVAL


# 实现：流式生成——逐 token 回调 on_token，返回完整回答文本
def stream_answer(
    messages: list[BaseMessage], on_token: Callable[[str], None] | None = None
) -> str:
    parts: list[str] = []
    for chunk in get_chat_model().stream(messages):
        text = chunk.content if isinstance(chunk.content, str) else ""
        if text:
            parts.append(text)
            if on_token:
                on_token(text)
    return "".join(parts)