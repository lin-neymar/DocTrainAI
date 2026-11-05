"""解析入库流水线：原件 → 切分 → 向量/全文 → doc_chunk。"""
from __future__ import annotations  # 延迟类型注解，支持模型互相引用

import uuid  # 生成唯一ID

from langchain_text_splitters import RecursiveCharacterTextSplitter  # 递归字符文本分片器
from sqlalchemy import delete, func, update  # SQLAlchemy DML操作、数据库函数
from sqlalchemy.orm import Session  # 数据库会话

from app.config import settings  # 项目全局配置
from app.core.exceptions import NotFoundError  # 自定义资源不存在异常
from app.models.ai_ext.chunk import DocChunk  # 文档分片向量表模型
from app.models.system.doc import Doc  # 文档主表模型
from app.services.ai_ext.embedding_client import embed_texts  # 批量向量化服务
from app.services.ai_ext.fulltext import jieba_tokenize_for_tsv  # jieba分词，用于PG全文检索
from app.services.ai_ext.loaders import load_documents  # 文件解析器，bytes转LangChain Document
from app.storage import get_storage  # 获取文件存储实例


# 解析并重建分片
def ingest_document(session: Session, doc_id: uuid.UUID) -> int:
    """解析指定文档并重建分片。返回写入的 chunk 数量。
    调用方负责外层事务/任务状态；本函数会 delete 旧 chunk 并 add 新行。
    """
    # 查询文档主记录，校验文档是否存在、已删除
    doc = session.get(Doc, doc_id)
    if doc is None or doc.is_deleted:
        raise NotFoundError("文档不存在")

    # 读取存储里的原始文件二进制内容
    raw = get_storage().read(doc.storage_key)
    # 根据后缀解析文件，得到LangChain Document列表
    source_docs = load_documents(raw, doc.extension)
    if not source_docs:
        raise ValueError("未能从原件提取到文本")

    # 初始化文本分片器，读取配置的分片大小、重叠度、分隔符
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", " ", "", "。", "？", "！", "；"],
    )
    # 对解析出来的文档执行分片
    pieces = splitter.split_documents(source_docs)
    # 过滤空文本，拿到干净的文本列表
    texts = [p.page_content.strip() for p in pieces if p.page_content.strip()]
    if not texts:
        raise ValueError("切分后无有效文本")

    # 删除该文档旧的分片数据，覆盖重建
    session.execute(delete(DocChunk).where(DocChunk.doc_id == doc_id))
    # 批量生成向量embedding
    vectors = embed_texts(texts)

    # 过滤掉空内容分片，和文本、向量一一对齐
    kept = [p for p in pieces if p.page_content.strip()]
    rows: list[DocChunk] = []
    # 循环组装分片记录
    for index, (text, vec, piece) in enumerate(zip(texts, vectors, kept, strict=True)):
        # 继承解析得到的位置元信息（页码、sheet、幻灯片号等）
        loc = dict(piece.metadata) if piece.metadata else {"ext": doc.extension}
        chunk = DocChunk(
            doc_id=doc_id,
            chunk_index=index,
            content=text,
            location=loc,
            embedding=vec,
        )
        session.add(chunk)
        rows.append(chunk)
    session.flush()  # 刷入会话，获取每条chunk自增id

    # 循环生成PostgreSQL全文检索tsvector字段
    for chunk in rows:
        token_str = jieba_tokenize_for_tsv(chunk.content)
        session.execute(
            update(DocChunk)
            .where(DocChunk.id == chunk.id)
            .values(content_tsv=func.to_tsvector("simple", token_str))
        )
    return len(rows)
