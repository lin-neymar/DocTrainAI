"""P1 学习：把 Markdown 切成 chunk（不入库、不 Embedding）。"""

from pathlib import Path # 路径库

from langchain_core.documents import Document # 文档库
from langchain_text_splitters import RecursiveCharacterTextSplitter # 文本分割器

# 实现：读取本地md，模拟 Loader 产出 Document
def laod_markdown(path:Path) -> list[Document]:
    #读取本地md文件（按照 utf-8 编码，把磁盘上的文件读成Python字符串）
    text=path.read_text(encoding='utf-8')
    #page_content=正文；metadata=位置/来源 （以后入库会用到）
    return [Document(page_content=text,metadata={'source':str(path),"ext":".md"})]

def main()->None:
    sample=Path(__file__).with_name("sample_leave.md")
    docs=laod_markdown(sample)

    # 实现：长度窗口切分；数值以后来自 CHUNK_SIZE / CHUNK_OVERLAP 配置
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=10, # 每个chunk的长度
        chunk_overlap=2, # 重叠部分长度
        separators=["\n\n", "\n", " ", ""] # 分割符
    )
    chunks=splitter.split_documents(docs)

    print(f"原文档数：{len(docs)};切分后 chunk 数：{len(chunks)}\n")
    for i,chunk in enumerate(chunks):
        print(f"----- chunk[{i}] len={len(chunk.page_content)} -----")
        print(chunk.page_content)
        print(f"metadata:{chunk.metadata}\n")

# 直接把这个文件当脚本跑，内置变量__name__为"__main__"
if __name__ == "__main__":
    main()