"""G4：数据库连接层（SQLAlchemy 2.0，同步模式）。

和 Node 对照：
  - engine          ≈ 连接池（mysql2/pg 池子的封装）
  - SessionLocal()  ≈ 一次业务操作里借一条连接，用完归还
  - Base            ≈ 所有「表模型」共同的父类
  - get_db()        ≈ FastAPI 的 Depends，每个请求自动开/关 Session
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# create_engine：根据 DATABASE_URL 创建连接池。
# pool_pre_ping=True：取连接前先 ping，避免 Docker 重启 Postgres 后用到死连接。
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# sessionmaker：工厂函数，调用 SessionLocal() 得到一个新的 Session 实例。
# autocommit=False：必须显式 commit 才写入（默认，安全）。
# autoflush=False：不自动 flush，由我们在 service 里控制节奏（项目统一约定）。
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """所有 ORM 模型（如 Dept、User）将来都继承这个类。

    Alembic 通过 Base.metadata 知道有哪些表要迁移。
    """


def get_db() -> Generator[Session, None, None]:
    """供 FastAPI 路由使用：Depends(get_db) 注入 db: Session。

    yield 之前：创建 Session（类似打开一次数据库事务上下文）。
    yield 之后：finally 里 close，连接还回池子。
    现在 G4 还没有路由用它，G5 建表、阶段 1 写接口时会频繁用到。
    """
    db = SessionLocal() # 1. 创建数据库会话，拿到db
    try:
        yield db # 2. 把db交给路由使用，【函数暂停！】
    finally:
        db.close() # 3. 路由使用完db后，关闭db，连接还回池子。
