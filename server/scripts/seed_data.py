"""阶段 1 种子数据清单（与 SERVER_SPEC 权限/内置角色/默认品牌一致）。

谁读这个文件？
  - 只有 scripts/seed.py（以及本仓库的 seed 测试）。

谁不该读？
  - app/api、app/services、鉴权依赖：它们只查 permission / role 表，避免「库里的码」和
    「代码里的清单」两套来源不一致。

改规约时：先改 SERVER_SPEC → 再改本文件 → 重跑 seed，内置角色的 role_permission 会被同步。
"""

from typing import Final

# 全公司唯一根节点：parent_id 为空；初始管理员、以后组织架构都挂在这棵树下
ROOT_DEPT_NAME: Final[str] = "总公司"

# 阶段 1 现行权限码；(code, 管理端展示名)
# code 是鉴权与 meta.permission 的唯一键；name 仅展示
PERMISSIONS: Final[list[tuple[str, str]]] = [
    ("dept:read", "部门查看"),
    ("dept:create", "部门创建"),
    ("dept:update", "部门更新"),
    ("dept:delete", "部门删除"),
    ("user:read", "用户查看"),
    ("user:create", "用户创建"),
    ("user:update", "用户更新"),
    ("user:delete", "用户删除"),
    ("user:reset_password", "重置用户密码"),
    ("role:read", "角色查看"),
    ("role:create", "角色创建"),
    ("role:update", "角色更新"),
    ("role:delete", "角色删除"),
    ("role:assign_perm", "分配角色权限"),
    ("doc:read", "文档查看"),
    ("doc:create", "文档上传"),
    ("doc:update", "文档更新"),
    ("doc:delete", "文档删除"),
    ("course:read", "课程查看"),
    ("course:create", "课程创建"),
    ("course:update", "课程更新"),
    ("course:delete", "课程删除"),
    ("course:attach_doc", "课程挂接文档"),
    ("system:read", "系统设置查看"),
    ("system:update", "系统设置更新"),
    # 管理范围开关：全公司；不自动获得全部文档/课程阅读权（方案 B）
    ("data:scope:all", "全公司数据范围"),
]

# 旧聚合码：停止绑定；seed 会将其 is_deleted=true（禁止物理删除权限行）
DEPRECATED_PERMISSION_CODES: Final[frozenset[str]] = frozenset(
    {
        "user:manage",
        "dept:manage",
        "role:manage",
        "doc:upload",
        "course:manage",
    }
)

# 便于测试与打印：现行码数量
ACTIVE_PERMISSION_COUNT: Final[int] = len(PERMISSIONS)

# (role code, 展示名, 绑定的 permission code 列表)
# role code 仅供 seed 定位内置角色；业务禁止 if role.code == "super_admin"
ROLES: Final[list[tuple[str, str, list[str]]]] = [
    (
        "super_admin",
        "超级管理员",
        [code for code, _ in PERMISSIONS],
    ),
    (
        "company_admin",
        "公司管理员",
        [
            "dept:read",
            "dept:create",
            "dept:update",
            "dept:delete",
            "user:read",
            "user:create",
            "user:update",
            "user:delete",
            "user:reset_password",
            "role:read",
            "doc:read",
            "doc:create",
            "doc:update",
            "doc:delete",
            "course:read",
            "course:create",
            "course:update",
            "course:delete",
            "course:attach_doc",
        ],
    ),
    (
        "dept_admin",
        "部门管理员",
        [
            "dept:read",
            "user:read",
            "user:create",
            "user:update",
            "user:delete",
            "user:reset_password",
            "role:read",
            "doc:read",
            "doc:create",
            "doc:update",
            "doc:delete",
            "course:read",
            "course:create",
            "course:update",
            "course:delete",
            "course:attach_doc",
        ],
    ),
    (
        "staff",
        "普通员工",
        [
            "dept:read",
            "doc:read",
            "course:read",
        ],
    ),
]

BUILTIN_ROLE_CODES: Final[frozenset[str]] = frozenset(code for code, _, _ in ROLES)
BUILTIN_ROLE_COUNT: Final[int] = len(ROLES)

# 全局品牌默认值（T2/T3；T4 Logo 可空，由超管后续上传）
DEFAULT_BRAND_SITE_NAME: Final[str] = "DocTrainAI"
DEFAULT_BRAND_LOGIN_SUBTITLE: Final[str] = "企业内部规章培训与知识助手"
