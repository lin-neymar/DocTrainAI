# SERVER_SPEC.md
> 后端编码规约。本文写明后续阶段的契约，避免阶段切换时改口。
> 未在 AI_ONBOARD.md 开放的阶段，只可阅读，禁止实现、禁止安装该阶段的依赖。

技术栈：Python 3.11、FastAPI、SQLAlchemy 2.0 同步会话、Pydantic v2、Alembic、PostgreSQL 16。
普通接口使用同步 `def` 和同步 Session。阶段 3 的 SSE 单独使用流式响应。

## 📁 目录
```
server/
├── alembic/
├── app/
│   ├── main.py                 # 应用入口，注册路由和异常处理
│   ├── config.py               # pydantic-settings，只从环境变量读配置
│   ├── database.py             # engine、Session、DeclarativeBase
│   ├── models/
│   │   ├── system/             # 用户、部门、角色、权限、文档、课程、系统品牌设置等
│   │   └── ai_ext/             # 阶段 2+：任务、分片、会话、消息、调用日志
│   ├── schemas/
│   │   ├── system/
│   │   └── ai_ext/
│   ├── api/
│   │   ├── system/
│   │   └── ai_ext/
│   ├── core/                   # JWT、当前用户、权限依赖、异常处理
│   ├── services/
│   │   ├── system/
│   │   └── ai_ext/
│   ├── workers/                # 阶段 2+：ARQ 任务。仍属于 server
│   └── utils/
├── scripts/
│   ├── seed.py                 # 权限码、内置角色、根部门、初始管理员、默认品牌
│   └── eval_retrieval.py       # 阶段 2+：命令行评估，不是在线服务
├── tests/
├── requirements.txt
├── alembic.ini
└── Dockerfile                  # 阶段 4 再添加
```

ORM 使用 `Mapped` 和 `mapped_column`。业务查询放在 service，不放在路由。

## 依赖白名单
阶段 1 可以安装：fastapi、uvicorn、sqlalchemy、pydantic-settings、alembic、psycopg、pgvector（仅驱动，阶段 1 不建向量列）、pyjwt、bcrypt、python-multipart、pytest、httpx、ruff。

阶段 2 才可以安装：langchain 及其加载、切分、Embedding 所需的最小依赖、arq、redis、jieba。不安装 LangGraph。

阶段 3 才可以安装：langgraph。对话调用使用已配置的兼容接口，不额外引入另一套 Agent 框架。

白名单外的包必须先确认。

## 🔴 阶段 1 领域模型
单公司部署，表上不设 `tenant_id`。组织默认深度：公司（根）→ 分公司 → 部门。

- 部门：树，`parent_id` 为空表示根。禁止形成环。软删除时若仍有未删除的子部门或用户，返回 409。
- 用户：恰好一个 `dept_id`，密码只存 bcrypt 哈希。软删除后不能登录。用户名在未删除记录中唯一。可选字段：`theme_primary`（个人主题主色，如 `#1F4B7A`；空则前端用默认色）。
- 角色与用户多对多。角色与权限码多对多。
- 权限码是字符串，种子脚本写入，业务代码从数据库读取，不在判断处手写第二份清单。
- 文档：归属一个部门（`dept_id`）。另有可见组织关联表（如 `doc_audience_dept`）：多行 `dept_id`，每行表示该节点**子树**可读。字段限于身份与文件元数据：标题、归属部门、原始文件名、扩展名、大小、存储键、sha256、上传人、时间、软删除。不含解析状态和正文。
- 课程：归属一个部门，与文档多对多；同样有 `course_audience_dept`。删除课程不删除文档。课程链接不改变文档的可见性。
- 系统品牌（全局一行或键值）：显示名、登录副文案、Logo 存储键。不含主题色（主题色在用户个人字段）。
- 原文件与 Logo 放在 `FILE_STORAGE_DIR`。软删除不立即清除磁盘文件。

可见性 / 范围函数签名之后不改：

- `get_accessible_dept_ids(user_id) -> list[UUID]`：管理范围。有 `data:scope:all` → 全部未删部门；否则用户所在部门及下级。
- `get_visible_doc_ids(user_id) -> list[UUID]`：阅读可见文档。规则：
  1. 无 `doc:read` → `[]`
  2. 用户所在部门落在该文档任一 audience 节点的子树内 → 可见
  3. **不再**因 `data:scope:all` 自动可见全部文档

课程列表/详情的可见规则与文档同构（需 `course:read` + audience 子树），可抽公共逻辑。函数放在 `services/system`，供阶段 2 检索调用 `get_visible_doc_ids`。

文档/课程写入约束（方案 B）：
- 归属部门必须在操作者 `get_accessible_dept_ids` 内。
- 每个 audience 节点必须 ⊆ 归属部门子树，且 ∈ 操作者可访问部门。
- 部门管理员创建/更新时：不接受客户端自定义 audience（或忽略），服务端固定为 `[操作者所在部门]`。
- 旧数据迁移：audience 初始等于原归属 `dept_id`。

## 🔴 权限码与种子角色
阶段 1 注册下列权限码（`资源:动作`）。旧码 `user:manage`、`dept:manage`、`role:manage`、`doc:upload`、`course:manage` **停止种子绑定并软删/停用**，不再授予任何内置角色。

| code | 含义 |
|---|---|
| `dept:read` | 部门列表/树/详情 |
| `dept:create` / `dept:update` / `dept:delete` | 部门写 |
| `user:read` / `user:create` / `user:update` / `user:delete` | 用户读写删 |
| `user:reset_password` | 重置他人密码 |
| `role:read` | 角色列表/详情；供用户表单勾选角色 |
| `role:create` / `role:update` / `role:delete` | 角色写 |
| `role:assign_perm` | 替换角色权限；`GET /permissions` |
| `doc:read` / `doc:create` / `doc:update` / `doc:delete` | 文档（create=上传；update=元数据与 audience） |
| `course:read` / `course:create` / `course:update` / `course:delete` | 课程 |
| `course:attach_doc` | 挂接文档 |
| `system:read` | 读取可管理的系统品牌（设置页） |
| `system:update` | 修改 T2/T3/T4（显示名、副文案、Logo） |
| `data:scope:all` | 管理范围为全公司；不自动可读全部内容 |

阶段 3 再注册 `agent:chat`。在那之前不种子、不判断这个码。

内置角色的 code 只给种子脚本使用：

| 角色 | code | 权限码 |
|---|---|---|
| 超级管理员 | `super_admin` | 阶段 1 全部上表权限码，含 `data:scope:all`、`system:read`、`system:update` |
| 公司管理员 | `company_admin` | `dept:*`（含 read）、`user:*`、`user:reset_password`、`role:read`、`doc:*`、`course:*`、`course:attach_doc`；**无** `role:create/update/delete/assign_perm`、**无** `system:*`、**无** `data:scope:all` |
| 部门管理员 | `dept_admin` | `dept:read`、`user:*`、`user:reset_password`、`role:read`、`doc:*`、`course:*`、`course:attach_doc`；**无** 部门写、**无** 角色写与配权、**无** `system:*`、**无** `data:scope:all` |
| 普通员工 | `staff` | `dept:read`、`doc:read`、`course:read` |

种子创建根部门（默认名「总公司」）。初始管理员来自 `INIT_ADMIN_USERNAME`、`INIT_ADMIN_PASSWORD`，归属根部门，角色为超级管理员。种子写入默认品牌：显示名 `DocTrainAI`、默认副文案、Logo 可空。

鉴权依赖只有两个入口：`get_current_user`、`require_permission(perm_code)`。数据范围与可见性调用上面的函数，不另写角色判断。

创建或将部门设为根（`parent_id` 为空）时：除对应 `dept:create`/`dept:update` 外，操作者还须持有 `data:scope:all`，否则 403。

个人主题色 T1：已登录用户更新自己的 `theme_primary` 即可，**不**要求 `system:update`。

## 🔴 阶段 1 接口
前缀 `/api/v1`。除登录、健康检查、**公开品牌只读**外都要登录。

- `GET /health`：不鉴权。
- `POST /auth/login`、`POST /auth/logout`、`GET /auth/me`：`/me` 须包含 `permission_codes`，以及个人 `theme_primary`（可空）。
- 部门：读需 `dept:read`；写需对应 `dept:create|update|delete`，并受管理范围约束。
- 用户：读需 `user:read`；写需对应细码；`PUT /users/{id}/password` 需 `user:reset_password`；均受管理范围约束。创建/更新可传 `role_ids`（操作者有 `user:update` 即可；拉角色列表另需 `role:read`）。
- 角色：读需 `role:read`；写需对应细码；`GET /permissions` 与 `PUT /roles/{id}/permissions` 需 `role:assign_perm`。
- 文档：读/下载需 `doc:read` + `get_visible_doc_ids`；上传 `doc:create`；改元数据与 audience `doc:update`；软删 `doc:delete`。写路径归属部门受管理范围约束。
- 课程：读需 `course:read` + 课程 audience 规则；写拆细码；`PUT /courses/{id}/docs` 需 `course:attach_doc`，文档须对操作者可见。
- 系统品牌：
  - `GET /system/brand`（或等价路径）：**公开只读**，返回显示名、副文案、Logo 访问信息，供登录页。不鉴权。
  - `GET /system/settings`：需 `system:read`，设置页用。
  - `PUT /system/settings`：需 `system:update`，改 T2/T3；Logo 可用单独 multipart 上传接口，同样需 `system:update`。
- 个人主题：`PUT /users/me/theme`（或挂在 `/auth/me` 的更新）：需登录，只能改当前用户 `theme_primary`。

列表分页：`page` 从 1，`page_size` 默认 20，最大 100。

不在可见集合内的详情/下载返回 404。

## 🔴 上传
业务文档：允许的扩展名和大小上限放在**环境变量**配置中。阶段 1 默认只允许 pdf、md，上限 20MB。校验扩展名和文件头。

Logo（T4）：单独限制较小体积与图片扩展名（如 png/jpg/webp），细则实现时写入配置常量或 env，不做成设置页可改项。

## 🔴 异常、删除与配置
全局异常处理器产出 PROJECT_SPEC 规定的响应体。预期内的 403、404、409 不打印堆栈。

业务查询默认排除 `is_deleted = true`。

阶段 1 的环境变量：

`APP_ENV`、`DATABASE_URL`、`JWT_SECRET`、`JWT_EXPIRE_MINUTES`、`FILE_STORAGE_DIR`、`FILE_MAX_MB`、`ALLOWED_EXTENSIONS`、`CORS_ORIGINS`、`INIT_ADMIN_USERNAME`、`INIT_ADMIN_PASSWORD`

`compose.yaml` 在阶段 1 只声明 PostgreSQL 16，镜像使用 `pgvector/pgvector`。数据库对外端口和账号写入 `.env.example`，不写进代码。

## 🔴 阶段 1 测试
pytest 至少覆盖：登录成功与失败、无令牌 401、缺权限码 403、audience 外文档详情 404、有 `doc:read` 且落在 audience 子树内可读、超管无 audience 时亦不可仅凭 `data:scope:all` 读到未授权文档、品牌公开接口可匿名读、无 `system:update` 不能改品牌、登录用户可改本人主题。

## 🔴 阶段 2 契约（现在不实现）
解析任务、分片、向量和全文索引入 `models/ai_ext`。文档主表不加状态列。任务状态为 `pending`、`running`、`succeeded`、`failed`，失败时保存错误摘要。

分片保存 `doc_id`、正文、位置（pdf 页码或 md 标题）和检索所需字段。md 先按标题切开，pdf 先按页切开，再按 `CHUNK_SIZE` 与 `CHUNK_OVERLAP` 控制长度。两个数值来自配置。

向量维度等于 `EMBEDDING_DIM`，必须与 `EMBEDDING_MODEL` 一致。更换维度时新建迁移，不在旧列里混放不同维度。

中文全文检索：写入和查询都用 jieba 分词，空格拼接后存入 `tsvector`（`simple` 配置）。不在数据库镜像中安装中文分词插件。

检索顺序固定：

1. 调用 `get_visible_doc_ids`。结果为空则直接返回空列表。
2. 只在这些文档内分别做向量检索和全文检索。
3. 两路分数各自归一化到 0–1，按 `HYBRID_VECTOR_WEIGHT` 合并。某一路没有结果时使用另一路。
4. 返回得分最高的 K 条。

检索接口复用 `doc:read`，不新增权限码。它仍然先走可见文档函数。

评估脚本 `scripts/eval_retrieval.py` 读取 JSONL。每行至少包含 `id`、`question`、`expected_doc_ids`。前 5 条结果的文档与期望文档有交集，记为命中。Recall@5 等于命中问题数除以问题数。阶段 2 交付可运行脚本和至少 5 条样例。脚本打印指标，不启动服务，也不提供 HTTP 接口。

阶段 2 增加 Redis，只给 ARQ 使用。解析由 worker 执行，路由只负责入队和查询任务状态。

阶段 2 增加的配置：`REDIS_URL`、`EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`、`CHUNK_SIZE`、`CHUNK_OVERLAP`、`HYBRID_VECTOR_WEIGHT`。

## 🔴 阶段 3 契约（现在不实现）
只做一个 LangGraph Agent，不拆多 Agent。意图是图里的一个节点，用一次模型调用或明确规则区分三类：需要检索的规章问题、与资料无关的闲聊、应拒答的问题。不训练分类模型。

需要检索时走阶段 2 的两路检索。闲聊不检索，也不编造文档引用。合并后的最高分低于 `ABSTAIN_SCORE_THRESHOLD` 时，不调用对话模型生成事实内容，返回配置中的固定拒答文案，并在消息上标记 `refused`。

系统指令和文档片段分区组装。片段标明为不可执行的参考资料。测试夹具中放一份含「忽略以上指令」的文档，断言回答不会执行其中的要求。

会话消息持久化。带入模型的历史默认最近 6 条，由 `MEMORY_TURNS_MESSAGES` 配置。引用结构固定包含 `doc_id`、`doc_title`、`chunk_id`、`location`、`snippet`。

每次回答写入调用日志：用户、会话、模型名、耗时、检索到的 `chunk_id` 列表、是否拒答。日志不保存完整文档正文和密钥。

SSE 事件只用这四种：

- `delta`：`{"text": "..."}`
- `citation`：一条引用对象
- `done`：`{"message_id": "...", "refused": false}`
- `error`：`{"message": "..."}`

对话接口需要 `agent:chat`。引用的文档仍必须属于该用户的可见集合。

评估 JSONL 增加可选字段 `expect_abstain`。阶段 3 增加引用命中率：回答引用的文档与 `expected_doc_ids` 有交集即命中。样例在阶段 3 结束前扩充到 30–50 条，并包含拒答样本。指标由同一脚本打印。

阶段 3 增加的配置：`CHAT_BASE_URL`、`CHAT_API_KEY`、`CHAT_MODEL`、`RETRIEVAL_TOP_K`、`ABSTAIN_SCORE_THRESHOLD`、`ABSTAIN_MESSAGE`、`MEMORY_TURNS_MESSAGES`。对话和 Embedding 可以指向同一个兼容服务，配置项仍然分开。

测试至少覆盖：低于拒答阈值时不调用对话模型；不可信文档夹具不能改写系统行为；没有 `agent:chat` 时返回 403。

## 🟡 SHOULD
1. Schema 按 Create、Update、Response 拆分。
2. 路由保持薄：收参数、调用依赖、调用 service、返回结果。
3. 模型调用设置超时。阶段 2 的解析任务失败后可重试，次数写入配置。
4. 提交前运行 ruff。

## ⚫ MUST NOT
1. `system` 下的模块禁止导入 `ai_ext`。
2. 禁止在路由函数中写解析、检索、提示词组装和模型调用。
3. 禁止修改已注册权限码的含义。新增码先改本规约再种子。
4. 禁止把检索阈值、分片长度和权重散落在业务代码里。
5. 禁止用角色 code 判断超级管理员。全量**管理**范围只来自 `data:scope:all`。
6. 禁止将 T1 个人主题做成仅超管可改；禁止将 T2/T3/T4 做成任意登录用户可改。
