"""按扩展名把文件二进制字节流解析为 LangChain Document 文档列表。"""
from __future__ import annotations  # 延迟类型注解，支持模型前向引用

from io import BytesIO  # 内存字节流，不用落盘文件直接读取bytes

from langchain_core.documents import Document  # LangChain文档对象，承载文本+元数据


def load_documents(content: bytes, extension: str) -> list[Document]:
    """主入口：根据文件后缀分发到对应解析函数
    :param content: 文件原始二进制数据
    :param extension: 文件后缀名，如 pdf / md
    """
    ext = (extension or "").lower().lstrip(".")  # 转小写、去掉开头的点，统一格式
    if ext == "md":
        return _load_md(content)
    if ext == "pdf":
        return _load_pdf(content)
    if ext == "docx":
        return _load_docx(content)
    if ext == "xlsx":
        return _load_xlsx(content)
    if ext == "pptx":
        return _load_pptx(content)
    raise ValueError(f"不支持的解析扩展名: {ext}")  # 后缀不在支持列表，抛出异常


def _load_md(content: bytes) -> list[Document]:
    """解析 Markdown：二进制转utf8文本，返回单个Document"""
    text = content.decode("utf-8")
    return [Document(page_content=text, metadata={"ext": "md"})]


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
