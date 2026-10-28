"""底座业务表 ORM。

Alembic 生成迁移时需要「import 到所有模型」，否则 autogenerate 发现不了新表。
因此每新增一张 system 表，在这里 import 一次（并加入 __all__）。
"""

from app.models.system.dept import Dept

__all__ = ["Dept"]
