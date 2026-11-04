"""中文全文：jieba 分词后交 Postgres to_tsvector('simple', ...)。

这个函数的用途：**中文文本先用 jieba 分词，拼接成空格隔开的词语字符串，
专门喂给 PostgreSQL 的 `to_tsvector('simple', ...)` 做全文检索（tsvector）**，
用来实现 BM25/Postgres 全文搜索，搭配你的向量检索组成混合检索
"""


from __future__ import annotations

import jieba


def jieba_tokenize_for_tsv(text: str) -> str:
    """返回空格分隔的词序列，供 simple 配置使用。"""
    return " ".join(w for w in jieba.cut(text or "") if w.strip())