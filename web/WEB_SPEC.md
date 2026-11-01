# WEB_SPEC.md
> 前端编码规约。本文包含后续阶段页面，便于界面和接口一次对齐。
> 未在 AI_ONBOARD.md 开放的阶段，禁止实现对应页面、store 和接口封装。

技术栈：Vue3、Vite、Element Plus、Pinia、Axios。界面语言为简体中文。

## 📁 src 目录
```
src/
├── api/
│   ├── system/                 # auth、dept、user、role、doc、course、settings
│   └── ai_ext/                 # 阶段 2+：解析状态、检索；阶段 3：对话
├── stores/
│   ├── user.ts                 # 当前用户与权限码的唯一存放处（可含 theme_primary）
│   └── brand.ts                # 可选：全局品牌（T2/T3/T4）缓存
├── router/
│   ├── routes/system/
│   └── routes/ai_ext/          # 阶段 3 才注册对话路由
├── components/
│   ├── common/
│   ├── system/
│   └── ai_ext/                 # 阶段 3：消息列表、引用卡片
├── views/
│   ├── system/                 # 登录、工作台、部门、用户、角色、文档、课程、系统设置
│   └── ai_ext/                 # 阶段 3：对话页
└── utils/
    ├── permission.ts           # hasPermission
    ├── request.ts              # Axios 实例与拦截器
    ├── theme.ts                # 应用个人主题主色到 CSS 变量 / Element
    └── sse.ts                  # 阶段 3：SSE 读取
```

阶段 1 不创建 `ai_ext` 的路由、页面和组件。可以先留出空目录，也可以到阶段 2 再创建。两种做法以「里面没有业务代码」为准。

## 依赖白名单
阶段 1：vue、vue-router、pinia、element-plus、axios、vite、eslint、prettier、typescript、vue-tsc，以及它们的官方配套插件。

阶段 3 的流式请求使用浏览器原生流，不额外引入 SSE 框架。白名单外的包先确认。

## 🔴 MUST
1. 用户资料和权限码只放在 `user` 这个 Pinia store。刷新后用 Access Token 调用 `/auth/me` 恢复。localStorage **默认只持久化 token**；允许额外持久化**当前用户个人主题色**（T1）以便首屏闪色处理，但不得持久化权限码、用户资料或业务列表。
2. 功能显隐只有 `hasPermission(permCode)`。它只查询 store 里的权限码。禁止 `role === 'admin'`、禁止比较角色中文名或角色 code。
3. 菜单来自前端静态路由。路由写 `meta.permission`，守卫和侧边栏都调用 `hasPermission`。不建菜单表，也不请求菜单接口。无 `meta.permission` 的项表示「已登录即可」（若该页仍需要，须在规约中写明；当前仅工作台等例外需谨慎新增）。
4. 未登录访问非公开业务路由时进入登录页。登录页为 `meta.public`。
5. Axios 请求自动带上 token。收到 401 时清除 token 和用户 store，跳转登录。403、409 和 500 按统一响应体里的 `message` 提示。成功时读取 `data`。
6. 列表页使用统一分页结构：`items`、`total`、`page`、`page_size`。
7. 表单用 Element Plus 规则校验必填项和格式，再提交。
8. 安全边界在后端。前端隐藏按钮只是交互。数据范围与方案 B 可见性不在前端计算。
9. `system` 下的视图和组件禁止导入 `components/ai_ext`、`views/ai_ext` 和对话 store。
10. 阶段 2 的文档页可以调用 `api/ai_ext` 显示解析状态。阶段 2 开放之前，文档页不调用这个接口。
11. **系统设置与主题**：
    - T1：任意已登录用户可在「系统设置」页的「个人外观」修改主题主色；调用本人主题接口；立即应用到 CSS 变量（默认主色 `#1F4B7A`）。顶栏不放置主题取色。
    - T2/T3/T4：仅持有 `system:update` 的用户可改；设置页内「全局品牌」区块按 `system:read` 可见、`system:update` 可改。登录页通过公开品牌接口展示显示名、副文案、Logo。
    - 禁止用角色 code 判断能否改品牌；只认 `system:update`。
12. **文档预览**：文档列表提供「查看」。调用预览接口（鉴权代下 blob）；pdf 用页内嵌入预览；md 用文本展示（阶段 1 不强制引入 markdown 渲染库）；office 预览流为 PDF，同样嵌入。关闭预览须释放对象 URL。阶段 1 不展示解析状态。

## 阶段页面
阶段 1：登录、工作台、部门树、用户、角色权限、文档上传与列表（含归属与可见组织、标题搜索、批量删除、查看预览；部门管理员无可见勾选；允许 pdf/md/docx/xlsx/pptx）、课程及挂接文档、系统设置（已登录可进：T1 人人可改；T2～T4 按码显隐）。文档列表不展示解析状态。

阶段 2：在现有文档列表增加解析状态。不新增知识库页面。

阶段 3：对话页放在 `views/ai_ext`。消息流式追加。引用卡片展示文档标题、位置和片段。拒答作为一条明确的助手消息展示。没有 `agent:chat` 的用户看不到对话入口。

SSE 的读取放在 `utils/sse.ts`。组件只消费已经解析好的 `delta`、`citation`、`done`、`error`。

## 🟡 SHOULD
1. 表格、确认弹窗和分页工具抽成 `components/common`，相同交互不各写一遍。
2. 接口函数全部放在 `src/api`。组件不直接创建 Axios 请求。
3. 保存前运行 Prettier 和 ESLint；改动后跑 typecheck。
4. 阶段 3 的长对话列表做虚拟滚动，并处理发送中、失败和可重试状态。
5. 管理台保持浅色侧栏；主色由 T1 个人主题驱动，默认 `#1F4B7A`。

## ⚫ MUST NOT
1. 禁止在前端保存或判断数据范围，也禁止用前端过滤代替文档可见性。
2. 禁止把接口根地址、密钥、模型名写进源码。接口根地址来自 Vite 环境变量。
3. 禁止把用户信息、权限码、文档内容长期放进 localStorage 或 sessionStorage（个人主题色除外）。
4. 禁止在 `system` 页面实现对话、引用卡片和 SSE。
5. 阶段 1 不做 Refresh Token，也不把令牌改成 Cookie。
6. 禁止在系统设置页提供 JWT、CORS、数据库、上传大小白名单等部署项编辑。

## 阶段 1 路由权限
| 页面 | meta.permission / 按钮码 |
|---|---|
| 工作台 | 已登录即可（无 meta.permission） |
| 部门管理 | `dept:read`；写按钮 `dept:create` / `dept:update` / `dept:delete`；根部门写另需后端校验 `data:scope:all` |
| 用户管理 | `user:read`；写按钮对应 `user:create` 等；重置密码 `user:reset_password`；角色勾选依赖 `role:read`；有 `user:delete` 时表格多选 + 批量删除（当前页） |
| 角色管理 | `role:assign_perm`（仅配置权限与角色维护入口）；无此码不进菜单。`role:read` 供其他页拉列表 |
| 文档管理 | `doc:read`；上传 `doc:create`；编辑 `doc:update`；删除 `doc:delete`；查看预览（`doc:read`）；标题搜索；有 `doc:delete` 时多选批量删 |
| 课程管理 | `course:read`；创建/编辑 `course:create`/`course:update`；删除 `course:delete`；挂接 `course:attach_doc`；标题搜索 |
| 系统设置 | 已登录即可（无 `meta.permission`）；页内品牌区 `system:read` / `system:update` |
| 个人主题 T1 | 无独立路由权限；设置页内已登录可改 |

对话页在阶段 3 使用 `agent:chat`。
