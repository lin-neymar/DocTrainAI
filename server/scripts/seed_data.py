"""C2：阶段 1 种子数据清单（与 SERVER_SPEC 权限/内置角色表一致）。

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

# 阶段 1 全部 9 个权限码；(code, 管理端展示名)
# code 是鉴权与 meta.permission 的唯一键；name 仅展示，可随产品文案调整
PERMISSIONS: Final[list[tuple[str, str]]] = [
    ("user:manage", "用户管理"),
    ("dept:manage", "部门管理"),
    ("role:manage", "角色管理"),
    ("doc:upload", "文档上传"),
    ("doc:read", "文档查看"),
    ("doc:delete", "文档删除"),
    ("course:manage", "课程管理"),
    ("course:read", "课程查看"),
    # 数据范围开关：拥有此码才看全公司；否则走「本部门及下级」（阶段 E 实现）
    ("data:scope:all", "全公司数据范围"),
]

# (role code, 展示名, 绑定的 permission code 列表)
# role code 仅供 seed 定位内置角色；业务禁止 if role.code == "super_admin" 这类分支
ROLES: Final[list[tuple[str, str, list[str]]]] = [
    (
        "super_admin",
        "超级管理员",
        [
            "user:manage",
            "dept:manage",
            "role:manage",
            "doc:upload",
            "doc:read",
            "doc:delete",
            "course:manage",
            "course:read",
            "data:scope:all",
        ],
    ),
    (
        "dept_admin",
        "部门管理员",
        [
            "user:manage",
            "doc:upload",
            "doc:read",
            "doc:delete",
            "course:manage",
            "course:read",
        ],
    ),
    (
        "staff",
        "普通员工",
        [
            "doc:read",
            "course:read",
        ],
    ),
]

# 当前 ROLES 里全部是内置角色；seed 会对这些 code 做 role_permission「删旧 + 按表重建」
BUILTIN_ROLE_CODES: Final[frozenset[str]] = frozenset(code for code, _, _ in ROLES)
