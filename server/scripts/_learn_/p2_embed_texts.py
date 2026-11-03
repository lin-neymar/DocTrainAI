"""P2 学习：调用兼容 Embedding API，观察向量维度与相似度（不入库）。"""

from __future__ import annotations #**让你可以在类定义里面，直接写 “自己这个类” 当作类型注解**
# 原理：所有类型注解**先不立刻解析求值，全部当成字符串存起来**，等到后面需要的时候再解析。# 惰性解析

import os 
from pathlib import Path

from langchain_openai import OpenAIEmbeddings

# 实现：纯 python 算余弦相似度，避免额外装 numpy
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def load_dotenv_simple(path:Path) -> None:
    """极简加载根目录 .env（学习用；正式项目用 pydantic-settings）。"""
    if not path.is_file(): # not是取反 is_file判断该路径**存在并且是普通文件**
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip() # strip() 方法用于移除字符串两端的空白字符（包括空格、制表符、换行符等）
        if not line or line.startswith("#") or "=" not in line:
            # 空行 / #注释行 / 没有=的行，跳过
            continue
        key,_,value =line.partition("=") # partition() 方法用于将字符串分割成三个部分：key、=、value
        key,value = key.strip(),value.strip().strip('"').strip("'") # strip() 方法用于移除字符串两端的空白字符（包括空格、制表符、换行符等）
        os.environ.setdefault(key,value) # setdefault() 方法用于设置字典的值，如果键不存在，则添加键值对，如果键存在，则不进行任何操作

def main() -> None:
    # 仓库根目录的 .env（server/scripts/_learn_/ -> 上三级到 DocTrainAi）
    root_env = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv_simple(root_env)

    base_url = os.environ.get("EMBEDDING_BASE_URL","").rstrip("/") # rstrip("/") 方法用于移除字符串末尾的斜杠
    api_key = os.environ.get("EMBEDDING_API_KEY","") #get() 方法用于获取字典的值，如果键不存在，则返回默认值
    model = os.environ.get("EMBEDDING_MODEL","") #get() 方法用于获取字典的值，如果键不存在，则返回默认值
    expect_dim = int(os.environ.get("EMBEDDING_DIM","0")) #int() 方法用于将字符串转换为整数

    if not base_url or not api_key or not model:
        raise SystemExit("请先配置 EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL")
    
    #实现： LangChain Embeddings; 业务里以后会封装进 service, 而不是散落调用
    embeddings = OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,  # 兼容通义等：不要先 tokenize 再发送
    )

    # 练习文本
    texts = [
        "司龄满五年的员工每年有十天带薪年假。",  # A：年假相关
        "年假天数与司龄有关，满五年可休十天。",  # B：与 A 相近
        "会议室高峰时段最多预约两小时。",        # C：无关主题
    ]

    vectors = embeddings.embed_documents(texts) # embed_documents() 方法用于将文本列表转换为向量列表
    dim = len(vectors[0]) # len() 方法用于获取列表的长度 ,dim是维度
    print(f"模型:{model}")
    print(f"实际维度: {dim}；配置 EMBEDDING_DIM: {expect_dim or '(未设)'}")
    if expect_dim and dim != expect_dim:
        print("⚠️ 维度与 EMBEDDING_DIM 不一致，正式入库前必须改配置或换模型")
    
    print(f"\n向量[0] 前 8 维预览: {vectors[0][:8]}")
    print(f"A≈B 相似度: {cosine_similarity(vectors[0], vectors[1]):.4f}")
    print(f"A≈C 相似度: {cosine_similarity(vectors[0], vectors[2]):.4f}")
    print("预期：A≈B 明显高于 A≈C（语义检索的直觉）")

if __name__ == "__main__":
    main()