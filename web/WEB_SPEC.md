# WEB_SPEC.md
> 前端编码规约。本文包含后续阶段页面，便于界面和接口一次对齐。
> 未在 AI_ONBOARD.md 开放的阶段，禁止实现对应页面、store 和接口封装。

技术栈：Vue3、Vite、Element Plus、Pinia、Axios。界面语言为简体中文。

## 📁 src 目录
```
src/
├── api/
│   ├── system/                 # auth、dept、user、role、doc、course
│   └── ai_ext/                 # 阶段 2+：解析状态、检索；阶段 3：对话
├── stores/
│   └── user.ts                 # 当前用户与权限码的唯一存放处
├── router/
│   ├── routes/system/
│   └── routes/ai_ext/          # 阶段 3 才注册对话路由
├── components/
│   ├── common/
│   ├── system/
│   └── ai_ext/                 # 阶段 3：消息列表、引用卡片
├── views/
│   ├── system/                 # 登录、部门、用户、角色、文档、课程
│   └── ai_ext/                 # 阶段 3：对话页
└── utils/
    ├── permission.ts           # hasPermission
    ├── request.ts              # Axios 实例与拦截器
    └── sse.ts                  # 阶段 3：SSE 读取
```

阶段 1 不创建 `ai_ext` 的路由、页面和组件。可以先留出空目录，也可以到阶段 2 再创建。两种做法以「里面没有业务代码」为准。

## 依赖白名单
阶段 1：vue、vue-router、pinia、element-plus、axios、vite、eslint、prettier，以及它们的官方配套插件。

阶段 3 的流式请求使用浏览器原生流，不额外引入 SSE 框架。白名单外的包先确认。

## 🔴 MUST
1. 用户资料和权限码只放在 `user` 这个 Pinia store。刷新后用 Access Token 调用 `/auth/me` 恢复。localStorage 只持久化 token，不放用户、权限和业务数据。
2. 功能显隐只有 `hasPermission(permCode)`。它只查询 store 里的权限码。禁止 `role === 'admin'`、禁止比较角色中文名或角色 code。
3. 菜单来自前端静态路由。路由写 `meta.permission`，守卫和侧边栏都调用 `hasPermission`。不建菜单表，也不请求菜单接口。
4. 没有 `meta.permission` 的业务页面不对普通登录用户开放。登录页和健康状态除外。未登录访问业务路由时进入登录页。
5. Axios 请求自动带上 token。收到 401 时清除 token 和用户 store，跳转登录。403、409 和 500 按统一响应体里的 `message` 提示。成功时读取 `data`。
6. 列表页使用统一分页结构：`items`、`total`、`page`、`page_size`。
7. 表单用 Element Plus 规则校验必填项和格式，再提交。
8. 安全边界在后端。前端隐藏按钮只是交互，不作为权限实现。数据范围不在前端计算。
9. `system` 下的视图和组件禁止导入 `components/ai_ext`、`views/ai_ext` 和对话 store。
10. 阶段 2 的文档页可以调用 `api/ai_ext` 显示解析状态（排队、处理中、成功、失败）。只取状态数据，不引入对话组件。阶段 2 开放之前，文档页不调用这个接口。

## 阶段页面
阶段 1：登录、部门树、用户、角色权限、文档上传与列表、课程及挂接文档。文档列表提供上传、下载、软删除，不展示解析状态。

阶段 2：在现有文档列表增加解析状态。不新增知识库页面。

阶段 3：对话页放在 `views/ai_ext`。消息流式追加。引用卡片展示文档标题、位置和片段。拒答作为一条明确的助手消息展示，不显示虚构引用。没有 `agent:chat` 的用户看不到对话入口。

SSE 的读取放在 `utils/sse.ts`。组件只消费已经解析好的 `delta`、`citation`、`done`、`error`。页面里不直接操作流读取器。

## 🟡 SHOULD
1. 表格、确认弹窗和分页工具抽成 `components/common`，相同交互不各写一遍。
2. 接口函数全部放在 `src/api`。组件不直接创建 Axios 请求。
3. 保存前运行 Prettier 和 ESLint。
4. 阶段 3 的长对话列表做虚拟滚动，并处理发送中、失败和可重试状态。

## ⚫ MUST NOT
1. 禁止在前端保存或判断数据范围，也禁止用前端过滤代替文档可见性。
2. 禁止把接口根地址、密钥、模型名写进源码。接口根地址来自 Vite 环境变量。
3. 禁止把用户信息、权限码、文档内容长期放进 localStorage 或 sessionStorage。
4. 禁止在 `system` 页面实现对话、引用卡片和 SSE。
5. 阶段 1 不做 Refresh Token，也不把令牌改成 Cookie。当前选择是短时 Access Token 加 `/me` 恢复，实现集中，便于先把权限链路跑通。

## 阶段 1 路由权限
| 页面 | meta.permission |
|---|---|
| 部门管理 | dept:manage；部门树的只读展示对已登录用户开放，写操作再校验该码 |
| 用户管理 | user:manage |
| 角色管理 | role:manage |
| 文档管理 | doc:read；上传按钮另需 doc:upload；删除按钮另需 doc:delete |
| 课程管理 | course:read；创建和编辑另需 course:manage |

对话页在阶段 3 使用 `agent:chat`。
