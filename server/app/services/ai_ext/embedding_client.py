"""Embedding 客户端（OpenAI 兼容；通义需关闭本地 tokenize）。"""

from __future__ import annotations  # 延迟类型注解，支持模型前向引用

from langchain_openai import OpenAIEmbeddings  # LangChain 兼容OpenAI协议的向量化封装

from app.config import settings  # 加载项目全局配置


# 获取向量嵌入实例
def get_embeddings()->OpenAIEmbeddings:
    """获取向量嵌入实例（兼容DashScope等OpenAI兼容接口）"""
    # 校验向量服务地址、密钥是否配置
    if not settings.embedding_base_url or not settings.embedding_api_key:
        #`raise` 是 Python 主动**抛出异常**的关键字
        raise RuntimeError("未配置 EMBEDDING_BASE_URL 或 EMBEDDING_API_KEY")
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url.rstrip("/"), # 移除末尾斜杠，避免拼接路径错误
        check_embedding_ctx_length=False, # 关闭内置上下文长度校验，交给上游模型控制
    )

# 批量嵌入文本
# DashScope text-embedding-v3 单次请求最多接受 10 条文本
EMBED_BATCH_SIZE = 10


# 批量嵌入文本：按 EMBED_BATCH_SIZE 分批调用，避免超过服务端 batch 上限
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        # embed_documents 方法：把一批文本批量转换为向量列表
        vectors.extend(get_embeddings().embed_documents(batch))

    # 合并后统一做维度校验，防御逻辑保持一处
    dim = settings.embedding_dim
    for i, vec in enumerate(vectors):
        if len(vec) != dim:
            raise RuntimeError(f"向量维度 {len(vec)} 与 EMBEDDING_DIM={dim} 不一致 (第 {i} 条)")
    return vectors
    