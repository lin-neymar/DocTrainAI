"""按扩展名把文件二进制字节流解析为 LangChain Document 文档列表。"""
from __future__ import annotations  # 延迟类型注解，支持模型前向引用

import re  # 标题行识别
from io import BytesIO  # 内存字节流，不用落盘文件直接读取bytes

from langchain_core.documents import Document  # LangChain文档对象，承载文本+元数据

# ATX 标题：1–6 级井号；_setext_ 下划线式标题少见，不支持
_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def load_documents(content: bytes, extension: str) -> list[Document]:
    """主入口：根据文件后缀分发到对应解析函数
    :param content: 文件原始二进制数据
    :param extension: 文件后缀名，如 pdf / md
    """
    ext = (extension or "").lower().lstrip(".")  # 转小写、去掉开头的点，统一格式
    loader = {
        "md": _load_md,
        "pdf": _load_pdf,
        "docx": _load_docx,
        "xlsx": _load_xlsx,
        "pptx": _load_pptx,
    }.get(ext)
    if loader is None:
        raise ValueError(f"不支持的解析扩展名: {ext}")  # 后缀不在支持列表，抛出异常
    docs = loader(content)
    # 统一清洗 NUL 字节：PostgreSQL text 字段禁止 \x00，部分 PDF 字体映射会产出，曾致写库必败
    for d in docs:
        d.page_content = d.page_content.replace("\x00", "")
    return docs


def _load_md(content: bytes) -> list[Document]:
    """解析 Markdown：按 ATX 标题切段，每段一个 Document。

    段内元数据记录最近一个标题（去井号后的纯文本），供分片 location 使用；
    首个标题前的引言/前言段不写 heading。围栏代码块（``` / ~~~）内的井号
    不视为标题。无标题文档退化为单篇整体。后续字符切分继承段元数据。
    """
    text = content.decode("utf-8")
    lines = text.splitlines(keepends=True)
    docs: list[Document] = []
    buf: list[str] = []
    heading = ""
    in_fence = False

    def flush() -> None:
        # 空段（只有空白）不入列表，避免产出无效 Document
        if "".join(buf).strip():
            meta = {"ext": "md"}
            if heading:
                meta["heading"] = heading
            docs.append(Document(page_content="".join(buf), metadata=meta))

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence  # 围栏开/关切换
        matched = None if in_fence else _ATX_HEADING.match(line)
        if matched:
            flush()
            buf = [line]  # 标题行留在段首，命中文本自带章节上下文
            heading = matched.group(2)
        else:
            buf.append(line)
    flush()
    return docs or [Document(page_content=text, metadata={"ext": "md"})]


def _load_pdf(content: bytes) -> list[Document]:
    """解析PDF：逐页提取文字，一页生成一个Document，记录页码"""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    docs: list[Document] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        docs.append(
            Document(page_content=text, metadata={"ext": "pdf", "page": i})
        )
    return docs


def _load_docx(content: bytes) -> list[Document]:
    """解析docx文档：读取所有段落文本，合并为一份Document"""
    from docx import Document as DocxFile

    doc = DocxFile(BytesIO(content))
    parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    text = "\n".join(parts)
    return [Document(page_content=text, metadata={"ext": "docx"})]


def _load_xlsx(content: bytes) -> list[Document]:
    """解析Excel：每个工作表生成一个Document，单元格用 | 分隔"""
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    docs: list[Document] = []
    for sheet in wb.worksheets:
        rows: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None and str(c).strip()]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            docs.append(
                Document(
                    page_content="\n".join(rows),
                    metadata={"ext": "xlsx", "sheet": sheet.title},
                )
            )
    return docs


def _load_pptx(content: bytes) -> list[Document]:
    """解析PPT：逐幻灯片提取文本，一页生成一个Document，记录幻灯片号"""
    from pptx import Presentation

    prs = Presentation(BytesIO(content))
    docs: list[Document] = []
    for i, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text.strip())
        text = "\n".join(p for p in parts if p)
        if text:
            docs.append(
                Document(page_content=text, metadata={"ext": "pptx", "slide": i})
            )
    return docs
