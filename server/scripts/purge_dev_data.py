"""开发库数据清理 CLI（开发命令，不是在线服务）。

保留 seed 基线：permission 全部、四个内置角色（code 见 SERVER_SPEC）及其权限绑定、
根部门（初始管理员所在部门）、初始管理员及其角色绑定、system_brand（全局品牌）。
其余业务数据全部清除：测试期造的自定义角色及绑定、部门树（除根）、其他用户及其
角色绑定、文档（含 audience、分片、解析任务）、课程（含挂接、audience），
以及被删文档的存储对象（原件与预览件）。

用法（在 server/ 目录）：
    .venv/bin/python -m scripts.purge_dev_data          # dry-run：只统计，不动数据
    .venv/bin/python -m scripts.purge_dev_data --yes    # 执行删除，并清理文档文件
    .venv/bin/python -m scripts.purge_dev_data --yes --keep-files   # 删数据但保留文件
"""

import argparse
import sys

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.storage import get_storage


def _counts(session) -> dict[str, int]:
    """统计各业务表行数（判断清理范围，dry-run 展示用）。"""
    tables = [
        "doc_chunk", "doc_parse_task", "doc_audience_dept", "doc",
        "course_audience_dept", "course_doc", "course",
        "user_role", "user", "dept", "role", "role_permission",
    ]
    return {t: session.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
            for t in tables}


def _resolve_keep(session) -> tuple:
    """定位必须保留的管理员与根部门；不存在则拒绝执行（防止误清 seed 前置）。"""
    admin = session.execute(
        text("SELECT id, dept_id FROM \"user\" WHERE username = :n AND is_deleted = false"),
        {"n": settings.init_admin_username},
    ).mappings().first()
    if admin is None:
        raise SystemExit(
            f"未找到初始管理员 {settings.init_admin_username}；"
            "请先执行 scripts/seed.py 再清理"
        )
    return admin["id"], admin["dept_id"]


def purge(dry_run: bool, keep_files: bool) -> int:
    # 双保险：绝不允许对着测试库跑（测试库由 pytest conftest 自动管理）
    if str(settings.database_url).rstrip("/").endswith("_test"):
        raise SystemExit("当前 DATABASE_URL 指向测试库，拒绝执行")

    with SessionLocal() as session:
        admin_id, root_dept_id = _resolve_keep(session)
        before = _counts(session)
        print(f"保留：管理员 id={admin_id}，根部门 id={root_dept_id}")
        print("当前行数：" + "  ".join(f"{k}={v}" for k, v in before.items()))

        if dry_run:
            print("\ndry-run 结束（未做任何修改）。加 --yes 执行删除。")
            return 0

        # 收集将被删除文档的存储对象键（数据删掉后就查不到了）
        file_keys = [
            row[key]
            for row in session.execute(
                text("SELECT storage_key, preview_storage_key FROM doc")
            ).mappings()
            for key in ("storage_key", "preview_storage_key")
            if row[key]
        ]

        # 依赖顺序：AI 扩展表 → 全部关联表 → 主表 → 角色绑定 → 用户 → 部门（叶子先删）
        session.execute(text("DELETE FROM doc_chunk"))
        session.execute(text("DELETE FROM doc_parse_task"))
        session.execute(text("DELETE FROM doc_audience_dept"))
        session.execute(text("DELETE FROM course_audience_dept"))
        session.execute(text("DELETE FROM course_doc"))
        session.execute(text("DELETE FROM doc"))
        session.execute(text("DELETE FROM course"))
        session.execute(
            text("DELETE FROM user_role WHERE user_id <> :admin"), {"admin": admin_id}
        )
        session.execute(text('DELETE FROM "user" WHERE id <> :admin'), {"admin": admin_id})
        # 角色基线：只保留四个内置角色（code 来自 SERVER_SPEC 种子表），
        # 测试期造的自定义角色及其权限绑定清除
        session.execute(
            text(
                "DELETE FROM role_permission WHERE role_id NOT IN ("
                "  SELECT id FROM role WHERE code IN ("
                "    'super_admin','company_admin','dept_admin','staff'))"
            )
        )
        session.execute(
            text(
                "DELETE FROM role WHERE code NOT IN ("
                "  'super_admin','company_admin','dept_admin','staff')"
            )
        )
        while True:
            result = session.execute(
                text(
                    "DELETE FROM dept WHERE id <> :keep AND NOT EXISTS ("
                    "  SELECT 1 FROM dept c WHERE c.parent_id = dept.id)"
                ),
                {"keep": root_dept_id},
            )
            if result.rowcount == 0:
                break
        # 根部门硬删残留的软删行不存在（上面只留 id=keep 一行），此处无需再处理
        session.commit()

        after = _counts(session)
        print("清理后：" + "  ".join(f"{k}={v}" for k, v in after.items()))

        if not keep_files and file_keys:
            storage = get_storage()
            # Local 实现 delete 幂等（文件不存在不报错），无需逐个容错
            for key in file_keys:
                storage.delete(key)
            print(f"存储对象：清理 {len(file_keys)} 个键（原件+预览件，含已不存在的）")

    print("完成。权限、角色、根部门、初始管理员与系统品牌保持不变。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="清理开发库业务数据（保留 seed 基线）")
    parser.add_argument("--yes", action="store_true", help="确认执行删除；缺省仅 dry-run")
    parser.add_argument("--keep-files", action="store_true", help="删数据但保留存储文件")
    args = parser.parse_args()
    return purge(dry_run=not args.yes, keep_files=args.keep_files)


if __name__ == "__main__":
    sys.exit(main())
