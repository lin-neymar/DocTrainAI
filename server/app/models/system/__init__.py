"""底座业务表 ORM。

Alembic 生成迁移时需要「import 到所有模型」，否则 autogenerate 发现不了新表。
因此每新增一张 system 表，在这里 import 一次（并加入 __all__）。
"""

from app.models.system.course import Course, CourseAudienceDept, CourseDoc
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.models.system.permission import Permission
from app.models.system.role import Role, RolePermission
from app.models.system.system_brand import SystemBrand
from app.models.system.user import User, UserRole

__all__ = [
    "Course",
    "CourseAudienceDept",
    "CourseDoc",
    "Dept",
    "Doc",
    "DocAudienceDept",
    "Permission",
    "Role",
    "RolePermission",
    "SystemBrand",
    "User",
    "UserRole",
]
