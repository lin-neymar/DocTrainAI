"""检索效果评估脚本（离线运行，不启动服务）。

读取 JSONL 评测集（每行 id / question / expected_doc_ids），
以初始管理员身份调用检索服务取前 5 条结果，
命中文档与期望文档有交集记为命中，输出逐题明细与 Recall@5。

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
from app.services.ai_ext.retrieval_service import search_chunks

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
        cases.append(case)
    return cases


# 实现：以初始管理员身份逐题检索，命中=前 5 条与期望文档有交集
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

        hit = 0
        for case in cases:
            items = search_chunks(
                session, user_id=admin.id, query=str(case["question"]), top_k=5
            )
            hit_doc_ids = {item["doc_id"] for item in items}
            expected = {UUID(str(x)) for x in case["expected_doc_ids"]}
            is_hit = bool(hit_doc_ids & expected)
            hit += int(is_hit)
            brief = [str(d)[:8] for d in sorted(hit_doc_ids)]
            mark = "命中" if is_hit else "未中"
            print(f"[{mark}] {case['id']} “{case['question']}” → 命中文档 {brief}")

    total = len(cases)
    recall = hit / total if total else 0.0
    print(f"\nRecall@5 = {hit}/{total} = {recall:.2%}")


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