"""阶段 2：混合检索契约测试（需 Postgres + pgvector；Embedding 用 mock 顶替）。

对应 SERVER_SPEC 阶段 2 的固定检索顺序：
  1. 无可见文档 → 直接返回空列表，绝不触碰 Embedding 与两路召回；
  2. 只在可见文档内检索：audience 外文档的分片绝不召回；
  3. 两路归一化加权合并、双路命中叠加、单路兜底（_merge 纯函数）；
  4. jieba 分词写入格式（纯函数，不依赖库）。

注意：fixture 的 skip 只包造数阶段，测试体内的断言失败不会被吞成 skip。
"""

import uuid
from types import SimpleNamespace

import bcrypt
import pytest
from sqlalchemy import delete, func, select, update

from app.config import settings
from app.database import SessionLocal
from app.models.ai_ext.chunk import DocChunk
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.ai_ext import retrieval_service
from app.services.ai_ext.fulltext import jieba_tokenize_for_tsv
from app.services.ai_ext.retrieval_service import _merge
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# 实现：造一个 embedding_dim 维的单位向量，index 位为 1，其余为 0
def _unit(index: int) -> list[float]:
    vec = [0.0] * settings.embedding_dim
    vec[index] = 1.0
    return vec


def _create_doc(
    session,
    *,
    title: str,
    dept_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    audience_dept_ids: list[uuid.UUID],
) -> Doc:
    doc = Doc(
        title=title,
        dept_id=dept_id,
        original_filename=f"{title}.md",
        extension="md",
        size_bytes=100,
        storage_key=f"test/{uuid.uuid4()}.md",
        sha256="c" * 64,
        uploaded_by=uploaded_by,
        is_deleted=False,
    )
    session.add(doc)
    session.flush()
    for aid in audience_dept_ids:
        session.add(DocAudienceDept(doc_id=doc.id, dept_id=aid))
    return doc


# 实现：写入分片并按解析流水线同款方式补 tsvector（jieba → simple 配置）
def _create_chunk(
    session, *, doc: Doc, content: str, embedding: list[float]
) -> DocChunk:
    chunk = DocChunk(
        doc_id=doc.id,
        chunk_index=0,
        content=content,
        location={"ext": "md"},
        embedding=embedding,
    )
    session.add(chunk)
    session.flush()
    session.execute(
        update(DocChunk)
        .where(DocChunk.id == chunk.id)
        .values(
            content_tsv=func.to_tsvector(
                "simple", jieba_tokenize_for_tsv(content)
            )
        )
    )
    return chunk


def _fake_chunk() -> DocChunk:
    """构造未落库的 ORM 对象，仅测 _merge 的纯分数逻辑。"""
    return DocChunk(
        id=uuid.uuid4(),
        doc_id=uuid.uuid4(),
        chunk_index=0,
        content="x",
    )


def _setup(session, registry: dict) -> SimpleNamespace:
    """造数：根下两个互斥分支；staff 在 A 分支；两篇文档各挂一个分片。"""
    run_seed(session)
    session.commit()
    admin = session.scalar(select(User).where(User.username == "admin"))
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert admin is not None and root is not None and staff_role is not None

    suffix = uuid.uuid4().hex[:8]
    branch_a = Dept(name=f"检索-A-{suffix}", parent_id=root.id, is_deleted=False)
    branch_b = Dept(name=f"检索-B-{suffix}", parent_id=root.id, is_deleted=False)
    session.add_all([branch_a, branch_b])
    session.flush()
    registry["dept_ids"] += [branch_a.id, branch_b.id]

    staff = User(
        username=f"rst_{suffix}",
        password_hash=_hash_password("pass"),
        dept_id=branch_a.id,
        is_deleted=False,
    )
    bare = User(
        username=f"rbr_{suffix}",
        password_hash=_hash_password("pass"),
        dept_id=root.id,
        is_deleted=False,
    )
    session.add_all([staff, bare])
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))
    registry["user_ids"] += [staff.id, bare.id]

    doc_a = _create_doc(
        session,
        title=f"rt-doc-a-{suffix}",
        dept_id=branch_a.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_a.id],
    )
    doc_b = _create_doc(
        session,
        title=f"rt-doc-b-{suffix}",
        dept_id=branch_b.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_b.id],
    )
    registry["doc_ids"] += [doc_a.id, doc_b.id]

    chunk_a = _create_chunk(
        session, doc=doc_a, content="员工年假申请规定与天数标准", embedding=_unit(0)
    )
    chunk_b = _create_chunk(
        session, doc=doc_b, content="年假申请流程补充说明", embedding=_unit(1)
    )
    session.commit()
    return SimpleNamespace(
        admin=admin,
        staff=staff,
        bare=bare,
        doc_a=doc_a,
        doc_b=doc_b,
        chunk_a=chunk_a,
        chunk_b_id=chunk_b.id,
    )


def _cleanup(registry: dict) -> None:
    """删除本文件造的数据，避免脏分片干扰 Recall@5 评估。"""
    with SessionLocal() as session:
        for doc_id in registry["doc_ids"]:
            session.execute(delete(DocChunk).where(DocChunk.doc_id == doc_id))
            session.execute(
                delete(DocAudienceDept).where(DocAudienceDept.doc_id == doc_id)
            )
            session.execute(delete(Doc).where(Doc.id == doc_id))
        for user_id in registry["user_ids"]:
            session.execute(delete(UserRole).where(UserRole.user_id == user_id))
            session.execute(delete(User).where(User.id == user_id))
        for dept_id in registry["dept_ids"]:
            session.execute(delete(Dept).where(Dept.id == dept_id))
        session.commit()


@pytest.fixture
def rt_env():
    registry: dict = {"dept_ids": [], "user_ids": [], "doc_ids": []}
    session = SessionLocal()
    try:
        env = _setup(session, registry)
    except Exception as exc:
        session.close()
        _cleanup(registry)
        pytest.skip(
            f"PostgreSQL/pgvector 未就绪，请 docker compose up -d 并 alembic upgrade head: {exc}"
        )
    yield session, env
    session.close()
    _cleanup(registry)


def test_search_returns_empty_without_visible_docs(rt_env, monkeypatch) -> None:
    """可见性前置：无 doc:read → 恒为空，且不触发 Embedding（不先全库召回）。"""
    session, env = rt_env

    def explode(texts: list[str]) -> list[list[float]]:
        raise AssertionError("可见文档为空时不应调用 Embedding")

    monkeypatch.setattr(retrieval_service, "embed_texts", explode)
    assert (
        retrieval_service.search_chunks(
            session, user_id=env.bare.id, query="年假", top_k=5
        )
        == []
    )


def test_search_only_recalls_visible_chunks(rt_env, monkeypatch) -> None:
    """staff 可读 A 分支文档；B 分支分片即便内容匹配也绝不召回。"""
    session, env = rt_env
    # 固定查询向量：与 doc_a 分片同向（cosine 距离 0），与 doc_b 分片正交
    query_vec = _unit(0)
    monkeypatch.setattr(
        retrieval_service, "embed_texts", lambda texts: [list(query_vec)]
    )

    items = retrieval_service.search_chunks(
        session, user_id=env.staff.id, query="年假 申请", top_k=5
    )
    hit_a = [item for item in items if item["chunk_id"] == env.chunk_a.id]
    assert hit_a, "可见文档的分片应被命中"
    assert hit_a[0]["doc_id"] == env.doc_a.id
    assert hit_a[0]["doc_title"] == env.doc_a.title
    assert hit_a[0]["score"] > 0
    # 核心安全断言：audience 外文档的分片绝不出现（向量路是 top_k 近邻，
    # 可见集内其他遗留分片也可能入列，但无权文档必须被前置过滤掉）
    assert env.doc_b.id not in {item["doc_id"] for item in items}
    assert env.chunk_b_id not in {item["chunk_id"] for item in items}


def test_hybrid_merge_weights_and_fallback(monkeypatch) -> None:
    """合并规则：min-max 归一化后按权重相加；单路兜底；全等分数视为满分。"""
    monkeypatch.setattr(settings, "hybrid_vector_weight", 0.7)
    a, b, c = _fake_chunk(), _fake_chunk(), _fake_chunk()
    vec_hits = [(a, 1.0), (b, 0.5)]
    ft_hits = [(b, 2.0), (c, 1.0)]

    ranked = _merge(vec_hits, ft_hits, top_k=5)
    order = [chunk.id for chunk, _ in ranked]
    scores = {chunk.id: score for chunk, score in ranked}
    # 归一化：a 向量满分 0.7；b 两路都命中 = 0.7*0 + 0.3*1；c 全文垫底 0.0
    assert order == [a.id, b.id, c.id]
    assert scores[a.id] == pytest.approx(0.7)
    assert scores[b.id] == pytest.approx(0.3)
    assert scores[c.id] == pytest.approx(0.0)

    # 某一路没有结果时使用另一路
    only_ft = _merge([], ft_hits, top_k=5)
    assert [chunk.id for chunk, _ in only_ft] == [b.id, c.id]
    only_vec = _merge(vec_hits, [], top_k=1)
    assert [chunk.id for chunk, _ in only_vec] == [a.id]

    # 单路内分数全等（或仅一条）时归一化按满分处理
    same = _merge([(a, 0.4)], [(a, 0.9)], top_k=5)
    assert same[0][1] == pytest.approx(1.0)


def test_jieba_tokenize_for_tsv_basic() -> None:
    """写入与查询共用分词：空格拼接、无空白 token；空串安全。

    只断言 jieba 默认词典切出的整词（如「申请」「提前」），不赌领域词切词结果。
    """
    tokens = jieba_tokenize_for_tsv("需要提前几天提交申请").split(" ")
    assert "申请" in tokens
    assert "提前" in tokens
    assert all(tok.strip() for tok in tokens)
    assert jieba_tokenize_for_tsv("") == ""
