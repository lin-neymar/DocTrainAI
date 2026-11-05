"""混合检索：可见性前置 → 向量 + 全文两路 → 归一化加权 → TopK。

检索顺序固定（SERVER_SPEC 阶段 2 契约）：
  1. get_visible_doc_ids；为空直接返回空列表。
  2. 只在可见文档内分别做向量检索与全文检索。
  3. 两路分数各自 min-max 归一化到 0–1，按 HYBRID_VECTOR_WEIGHT 合并。
  4. 返回得分最高的 K 条。
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select  # SQLAlchemy功能函数、选择查询
from sqlalchemy.orm import Session  # SQLAlchemy会话

from app.config import settings  # 配置设置
from app.core.exceptions import ValidationFailedError  # 验证失败异常
from app.models.ai_ext.chunk import DocChunk  # 文档分片模型
from app.models.system.doc import Doc  # 文档模型
from app.services.ai_ext.embedding_client import embed_texts  # 嵌入文本服务
from app.services.ai_ext.fulltext import jieba_tokenize_for_tsv  # 全文检索服务
from app.services.system.scope_service import get_visible_doc_ids  # 获取可见文档ID


# 实现：混合检索入口；返回 [{chunk_id, doc_id, doc_title, ...}]，score 降序
def search_chunks(
    session: Session, *, user_id: uuid.UUID, query: str, top_k: int
) -> list[dict]:
    query = query.strip()
    if not query:
        raise ValidationFailedError("检索词不能为空")

    # 1. 可见性前置：结果为空直接返回，绝不先全库召回再过滤
    visible = get_visible_doc_ids(session, user_id)
    if not visible:
        return []

    # 2. 两路独立候选
    vec_hits = _vector_search(session, visible, query, top_k)
    ft_hits = _fulltext_search(session, visible, query, top_k)

    # 3 + 4. 归一化加权合并后取 TopK，并补上文档标题
    ranked = _merge(vec_hits, ft_hits, top_k)
    return _to_items(session, ranked)

# 实现：向量路——pgvector 余弦相似度（相似度 = 1 - 余弦距离）
def _vector_search(
    session: Session, doc_ids: list[uuid.UUID], query: str, limit: int
) -> list[tuple[DocChunk, float]]:
    vec = embed_texts([query])[0]
    distance = DocChunk.embedding.cosine_distance(vec)
    rows = session.execute(
        select(DocChunk, (1 - distance).label("score"))
        .where(DocChunk.doc_id.in_(doc_ids), DocChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    ).all()
    return [(row[0], float(row[1])) for row in rows]

# 实现：全文路——jieba 分词后 plainto_tsquery('simple') 与写入端配置一致
def _fulltext_search(
    session: Session, doc_ids: list[uuid.UUID], query: str, limit: int
) -> list[tuple[DocChunk, float]]:
    ts_query = func.plainto_tsquery("simple", jieba_tokenize_for_tsv(query))
    rank = func.ts_rank(DocChunk.content_tsv, ts_query)
    rows = session.execute(
        select(DocChunk, rank.label("score"))
        .where(
            DocChunk.doc_id.in_(doc_ids),
            DocChunk.content_tsv.op("@@")(ts_query),
        )
        .order_by(rank.desc())
        .limit(limit)
    ).all()
    return [(row[0], float(row[1])) for row in rows]

# 实现：min-max 归一化到 0–1；单条或全等分数时视为满分
def _minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]

# 实现：单路命中时的兜底——归一化后按分排序取前 K
def _single_route_rank(
    hits: list[tuple[DocChunk, float]], top_k: int
) -> list[tuple[DocChunk, float]]:
    norm = _minmax([s for _, s in hits])
    ranked = sorted(
        zip((c for c, _ in hits), norm), key=lambda pair: pair[1], reverse=True
    )
    return ranked[:top_k]

# 实现：两路加权合并——同一分片两路都命中时分数相加
def _merge(
    vec_hits: list[tuple[DocChunk, float]],
    ft_hits: list[tuple[DocChunk, float]],
    top_k: int,
) -> list[tuple[DocChunk, float]]:
    if not vec_hits:
        return _single_route_rank(ft_hits, top_k)
    if not ft_hits:
        return _single_route_rank(vec_hits, top_k)

    v_norm = _minmax([s for _, s in vec_hits])
    f_norm = _minmax([s for _, s in ft_hits])
    w_vec = settings.hybrid_vector_weight

    merged: dict[uuid.UUID, tuple[DocChunk, float]] = {}
    for (chunk, _), v_score in zip(vec_hits, v_norm):
        merged[chunk.id] = (chunk, w_vec * v_score)
    for (chunk, _), f_score in zip(ft_hits, f_norm):
        prev = merged.get(chunk.id)
        if prev is None:
            merged[chunk.id] = (chunk, (1 - w_vec) * f_score)
        else:
            merged[chunk.id] = (chunk, prev[1] + (1 - w_vec) * f_score)

    ranked = sorted(merged.values(), key=lambda item: item[1], reverse=True)
    return ranked[:top_k]

# 实现：命中分片补文档标题并组装响应 dict
def _to_items(
    session: Session, ranked: list[tuple[DocChunk, float]]
) -> list[dict]:
    doc_ids = {chunk.doc_id for chunk, _ in ranked}
    titles = dict(
        session.execute(
            select(Doc.id, Doc.title).where(Doc.id.in_(doc_ids))
        ).all()
    )
    items: list[dict] = []
    for chunk, score in ranked:
        items.append(
            {
                "chunk_id": chunk.id,
                "doc_id": chunk.doc_id,
                "doc_title": titles.get(chunk.doc_id, ""),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "location": chunk.location,
                "score": round(score, 6),
            }
        )
    return items