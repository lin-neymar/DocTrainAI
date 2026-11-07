"""对话效果评估脚本（离线运行，不启动服务）。

读取 JSONL 评测集（每行 id / question / expected_doc_ids / 可选 expect_abstain），
以初始管理员身份逐题走 Agent（对话模型用脚本内置假客户端，检索与拒答判断走真实实现），
输出逐题明细与三项指标：
  - Recall@5：非拒答样本，检索前 5 条与期望文档有交集即命中（与阶段 2 相同）；
  - 引用命中率：非拒答且未拒答样本，回答引用文档与期望文档有交集即命中；
  - 拒答正确率：expect_abstain=true 的样本回答 refused=true 记正确。

用法（在 server/ 目录）：
    .venv/bin/python -m scripts.eval_retrieval scripts/eval_samples.jsonl
    .venv/bin/python -m scripts.eval_retrieval --list-docs   # 列出库内文档，供构建评测集
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models.system.doc import Doc
from app.models.system.user import User
from app.services.ai_ext import agent_graph
from app.services.ai_ext.retrieval_service import search_chunks

REQUIRED_FIELDS = ("id", "question", "expected_doc_ids")

# 假模型生成的固定回答文本（只验证检索与拒答链路，不评估生成质量）
FAKE_ANSWER = "（脚本化回答）"

REQUIRED_FIELDS = ("id", "question", "expected_doc_ids")


# 实现：读取并校验 JSONL 评测集；格式错误打印行号后以退出码 1 终止
def _load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"第 {lineno} 行不是合法 JSON: {exc}", file=sys.stderr)
            raise SystemExit(1)
        missing = [f for f in REQUIRED_FIELDS if f not in case]
        if missing:
            print(f"第 {lineno} 行缺少字段: {missing}", file=sys.stderr)
            raise SystemExit(1)
        if not str(case["question"]).strip():
            print(f"第 {lineno} 行 question 为空", file=sys.stderr)
            raise SystemExit(1)
        if not isinstance(case["expected_doc_ids"], list) or not case["expected_doc_ids"]:
            print(f"第 {lineno} 行 expected_doc_ids 须为非空数组", file=sys.stderr)
            raise SystemExit(1)
        if "expect_abstain" in case and not isinstance(case["expect_abstain"], bool):
            print(f"第 {lineno} 行 expect_abstain 须为布尔", file=sys.stderr)
            raise SystemExit(1)
        cases.append(case)
    return cases


# 实现：安装脚本内置假模型——分类按样例 expect_abstain 决定，生成返回固定文本
def _install_fake_model(cases: list[dict]) -> None:
    expect_by_question = {
        str(case["question"]): bool(case.get("expect_abstain", False))
        for case in cases
    }

    def fake_classify(question: str) -> str:
        return "refuse" if expect_by_question.get(question, False) else "retrieval"

    def fake_stream(messages, on_token=None) -> str:
        if on_token:
            on_token(FAKE_ANSWER)
        return FAKE_ANSWER

    def fake_relevance(question: str, chunks: list[dict]) -> bool:
        # 期望拒答的样本：资料判为无关 → 走 refuse（与真实链路拒答路径一致）
        return not expect_by_question.get(question, False)

    agent_graph.classify_intent = fake_classify
    agent_graph.stream_answer = fake_stream
    agent_graph.check_relevance = fake_relevance


# 实现：三指标汇总——返回各指标 (命中数, 总数)
def _calc_metrics(results: list[dict]) -> dict[str, tuple[int, int]]:
    non_abstain = [r for r in results if not r["expect_abstain"]]
    answered = [r for r in non_abstain if not r["refused"]]
    abstain_cases = [r for r in results if r["expect_abstain"]]
    return {
        "recall": (
            sum(1 for r in non_abstain if r["retrieval_hit"]),
            len(non_abstain),
        ),
        "citation": (
            sum(1 for r in answered if r["citation_hit"]),
            len(answered),
        ),
        "abstain": (
            sum(1 for r in abstain_cases if r["refused"]),
            len(abstain_cases),
        ),
    }


# 实现：以初始管理员身份逐题走 Agent，输出明细与三指标
def run_eval(cases: list[dict]) -> None:
    with SessionLocal() as session:
        admin = session.scalar(
            select(User).where(
                User.username == settings.init_admin_username,
                User.is_deleted.is_(False),
            )
        )
        if admin is None:
            print("初始管理员不存在，请先执行 .venv/bin/python -m scripts.seed", file=sys.stderr)
            raise SystemExit(1)

        _install_fake_model(cases)
        results: list[dict] = []
        for case in cases:
            question = str(case["question"])
            expect_abstain = bool(case.get("expect_abstain", False))
            expected = {UUID(str(x)) for x in case["expected_doc_ids"]}

            # Recall@5：只在非拒答样本检索（与阶段 2 相同）
            retrieval_hit: bool | None = None
            if not expect_abstain:
                items = search_chunks(session, user_id=admin.id, query=question, top_k=5)
                retrieval_hit = bool({item["doc_id"] for item in items} & expected)

            result = agent_graph.run_agent(
                session, user_id=admin.id, question=question, history=[]
            )
            refused = bool(result["refused"])

            # 引用命中：未拒答样本，引用文档与期望文档有交集
            citation_hit: bool | None = None
            if not expect_abstain and not refused:
                cited = {UUID(str(c["doc_id"])) for c in result.get("citations") or []}
                citation_hit = bool(cited & expected)

            results.append(
                {
                    "id": case["id"],
                    "expect_abstain": expect_abstain,
                    "retrieval_hit": retrieval_hit,
                    "citation_hit": citation_hit,
                    "refused": refused,
                }
            )
            if expect_abstain:
                mark = "正确拒答" if refused else "错误未拒答"
            else:
                mark = "命中" if retrieval_hit else "未中"
            print(f"[{mark}] {case['id']} “{question}” refused={refused}")

    metrics = _calc_metrics(results)
    recall_hit, recall_total = metrics["recall"]
    citation_hit, citation_total = metrics["citation"]
    abstain_hit, abstain_total = metrics["abstain"]
    recall = recall_hit / recall_total if recall_total else 0.0
    citation = citation_hit / citation_total if citation_total else 0.0
    abstain = abstain_hit / abstain_total if abstain_total else 0.0
    print(f"\nRecall@5 = {recall_hit}/{recall_total} = {recall:.2%}")
    print(f"引用命中率 = {citation_hit}/{citation_total} = {citation:.2%}")
    print(f"拒答正确率 = {abstain_hit}/{abstain_total} = {abstain:.2%}")


# 实现：列出库内未删除文档的 id 与标题，供人工构建评测集
def list_docs() -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(Doc.id, Doc.title)
            .where(Doc.is_deleted.is_(False))
            .order_by(Doc.created_at)
        ).all()
    if not rows:
        print("当前库中没有文档，请先上传评测文档并等待解析完成")
        return
    for doc_id, title in rows:
        print(f"{doc_id}\t{title}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检索效果评估（Recall@5）")
    parser.add_argument("cases", nargs="?", help="评测集 JSONL 路径")
    parser.add_argument("--list-docs", action="store_true", help="列出库内文档，供构建评测集")
    args = parser.parse_args()

    if args.list_docs:
        list_docs()
        return 0
    if not args.cases:
        parser.error("请提供评测集路径，或使用 --list-docs")
    run_eval(_load_cases(Path(args.cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())