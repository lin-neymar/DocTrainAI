"""阶段 2：loaders 的 Markdown 标题切段测试（纯函数，无需数据库）。

契约点：md 分片 location 需含标题（SERVER_SPEC 位置示例 {"ext":"md","heading":...}），
标题切段在 loader 完成，下游切分继承段元数据。
"""

from app.services.ai_ext.loaders import load_documents


def test_md_splits_by_heading_with_metadata() -> None:
    """按 ATX 标题切段：每段一个 Document，heading 为去井号纯文本。"""
    content = (
        "# 考勤管理制度\n"
        "本制度适用于全员。\n"
        "\n"
        "## 年假天数\n"
        "工龄满 1 年不满 10 年的，年假 5 天。\n"
        "\n"
        "## 病假申请\n"
        "需提前提交医院证明。\n"
    ).encode("utf-8")

    docs = load_documents(content, "md")

    # 文件首行即标题：无引言段，三个标题切出三个 Document
    assert [d.metadata.get("heading") for d in docs] == [
        "考勤管理制度",
        "年假天数",
        "病假申请",
    ]
    assert all(d.metadata["ext"] == "md" for d in docs)
    # 标题行保留在段首，命中文本自带章节上下文
    assert docs[1].page_content.startswith("## 年假天数")
    assert "年假 5 天" in docs[1].page_content
    assert "医院证明" not in docs[1].page_content


def test_md_heading_inside_code_fence_is_not_a_section() -> None:
    """围栏代码块内的井号不切段：shell 注释、标题示例都留在原段里。"""
    content = (
        "# 部署说明\n"
        "执行以下脚本：\n"
        "```bash\n"
        "# 这是注释不是标题\n"
        "echo ok\n"
        "```\n"
        "完成后重启服务。\n"
    ).encode("utf-8")

    docs = load_documents(content, "md")

    assert len(docs) == 1
    assert docs[0].metadata["heading"] == "部署说明"
    assert "# 这是注释不是标题" in docs[0].page_content


def test_md_without_heading_falls_back_to_single_doc() -> None:
    """无标题文档退化为单篇整体，与旧行为一致。"""
    docs = load_documents("纯文本说明，没有任何标题。\n第二行。\n".encode("utf-8"), "md")

    assert len(docs) == 1
    assert docs[0].metadata == {"ext": "md"}


def test_md_hash_edge_cases_not_headings() -> None:
    """井号后无空格、七级井号、行内列表井号都不切段。"""
    content = (
        "#没空格不是标题\n"
        "####### 七个井号不是标题\n"
        "- # 列表项里的井号不是标题\n"
    ).encode("utf-8")

    docs = load_documents(content, "md")

    assert len(docs) == 1
    assert "heading" not in docs[0].metadata
