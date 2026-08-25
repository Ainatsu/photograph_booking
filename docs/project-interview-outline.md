# 摄影师预约平台：项目实战面试目录

> 这是一份基于当前仓库代码整理的互动式面试目录，不是脱离项目的通用八股题库。
> 后续面试将按照题号逐题进行：我提问 → 你回答 → 我评价答案、指出遗漏并给出更准确的表达 → 你说“下一道”后继续。

## 一、面试方式与评价标准

### 1. 互动规则

- 默认从 `B-01` 开始，先从项目基础与系统地图进入。
- 一次只问一道题，不提前公布标准答案。
- 你可以说“提示”，我会给出逐级提示；也可以说“跳过”，稍后再回来。
- 你回答后，我会从以下方面评价：正确性、完整性、项目结合度、表达清晰度、工程意识。
- 每道题评价后，我会补充：推荐答案、容易混淆的点、对应代码位置和可继续追问的问题。
- 你说“下一道”后才进入下一题；你说“换板块”可以切换到指定章节。

### 2. 题目难度

- `★`：基础认知，适合热身。
- `★★`：能够结合代码解释实现。
- `★★★`：需要分析设计取舍、边界和失败场景。
- `★★★★`：架构设计、性能、安全或生产化追问。

### 3. 面试主线

项目主线是：客户浏览摄影师、作品和套餐 → 创建预约订单 → 摄影师确认 → 支付 → 沟通 → 交付 → 验收和评价。

项目同时包含：

- FastAPI + SQLAlchemy + Alembic 的后端；
- Vue 3 用户端、Vue 3 管理端和 Ionic/Vue + Capacitor 移动端；
- JWT 鉴权、角色权限、订单状态机、支付/交付/争议处理；
- Redis/fakeredis 缓存、WebSocket 消息推送、Local/MinIO 文件存储；
- 规则式/混合意图识别、Tool Calling、混合 RAG、多模态检索和 Agent 审计。

---

## 二、板块 A：项目概览与基础能力

### A1. 项目理解

- `A-01` ★ 请用 1 分钟介绍这个摄影师预约平台解决的业务问题。
- `A-02` ★ 项目有哪些角色？客户、摄影师和管理员分别能做什么？
- `A-03` ★ 用户端、管理端、移动端分别承担什么职责？为什么没有合并成一个前端？
- `A-04` ★ 请画出一次“浏览摄影师到完成订单”的端到端链路。
- `A-05` ★ 仓库中 `backend`、`frontend`、`admin-frontend`、`mobile-app`、`docs`、`assets`、`uploads` 分别是什么？
- `A-06` ★ 本项目属于单体、微服务还是前后端分离架构？请说明判断依据。
- `A-07` ★ `README.md` 中本地默认使用 SQLite，而 Docker 使用 PostgreSQL，为什么这样设计？
- `A-08` ★ `docker-compose.yml` 中为什么同时启动 PostgreSQL、Redis 和 MinIO？

### A2. Python / Web 基础

- `A-09` ★ FastAPI 与传统同步 Web 框架相比有什么特点？
- `A-10` ★ Python 中同步函数、异步函数和协程有什么区别？项目中哪些地方适合异步？
- `A-11` ★ 什么是依赖注入？`backend/app/api/deps.py` 中的 `get_db`、`get_current_user` 如何工作？
- `A-12` ★ HTTP 中 GET、POST、PUT/PATCH、DELETE 的语义分别是什么？
- `A-13` ★ 什么是幂等性？查询、创建订单、支付回调分别应该如何考虑幂等？
- `A-14` ★ 你如何区分 400、401、403、404、409、422 和 500？项目中哪些场景对应这些状态码？
- `A-15` ★ 什么是 RESTful API？本项目 `/api/v1` 版本前缀有什么价值？

---

## 三、板块 B：后端架构与 API 设计

### B1. 应用入口与分层

- `B-01` ★ `backend/app/main.py` 为什么可以看作后端的“总装配中心”？
- `B-02` ★ `router`、`service`、`model`、`schema` 四层分别负责什么？为什么不把业务逻辑都写在接口函数里？
- `B-03` ★ FastAPI 的 lifespan 在本项目启动和关闭时做了哪些事情？
- `B-04` ★ 启动时自动执行 Alembic migration 有什么收益和风险？生产环境为什么设置 `AUTO_RUN_MIGRATIONS=false`？
- `B-05` ★ CORS 配置中的 `allow_origins`、`allow_credentials`、`allow_methods`、`allow_headers` 各有什么影响？
- `B-06` ★ 项目如何统一处理请求校验错误？`RequestValidationError` 处理器有哪些优点和隐患？
- `B-07` ★ 为什么使用 Pydantic Schema 做输入输出边界，而不是直接返回 SQLAlchemy Model？

### B2. API 与业务服务

- `B-08` ★ 以创建订单接口为例，请说明请求从路由到数据库提交经过哪些层。
- `B-09` ★ 分页参数 `skip` 和 `limit` 有什么问题？生产环境如何防止过大 limit 和深分页？
- `B-10` ★ 如何设计一个“客户查看自己的订单、摄影师查看分配给自己的订单”的接口，避免越权？
- `B-11` ★ 为什么服务层中经常同时做权限检查、状态检查、事务写入和事件记录？
- `B-12` ★ 如果一个接口要更新订单、写订单事件、发通知，三步中第二步失败时应该怎么办？
- `B-13` ★ 什么时候应该返回业务错误，什么时候应该抛出未处理异常交给 500？
- `B-14` ★ 如果需要兼容旧客户端 API，你会如何做版本兼容，而不是直接修改旧接口语义？

---

## 四、板块 C：认证、安全与权限

### C1. 登录与 JWT

- `C-01` ★ 请描述一次登录请求从前端到 JWT 返回的完整过程。
- `C-02` ★ 为什么密码使用 bcrypt 哈希，而不能使用 MD5/SHA-256 直接存储？
- `C-03` ★ JWT 的 Header、Payload、Signature 分别是什么？JWT 加密了吗？
- `C-04` ★ 项目中 `iat`、`exp`、`sub`、`ver` 这些 Claims 有什么作用？
- `C-05` ★ `Authorization: Bearer <token>` 的含义是什么？FastAPI 如何解析它？
- `C-06` ★ `token_version` 如何让用户的旧 Token 全部失效？这个方案的代价是什么？
- `C-07` ★ access token 放在 `localStorage` 有哪些 XSS 风险？你会如何改进？
- `C-08` ★ Token 过期、用户被禁用、Token 版本不一致，后端分别应该返回什么？

### C2. 身份、角色与越权

- `C-09` ★ `get_current_user` 和 `get_current_active_user` 为什么要拆开？
- `C-10` ★ 如何实现客户、摄影师、管理员三类角色权限？角色校验应该放在哪一层？
- `C-11` ★ 仅校验 `is_admin` 是否足够？如何防止用户修改请求体中的 user_id 访问他人资源？
- `C-12` ★ 摄影师申请审核通过前，哪些接口应该被限制？
- `C-13` ★ 管理员取消订单和订单参与者取消订单，权限和审计上有什么差别？
- `C-14` ★ 验证码发送接口如何防刷？请结合项目中的 TTL、重试次数和小时/日限额回答。

---

## 五、板块 D：数据库、SQLAlchemy 与数据一致性

### D1. 数据模型

- `D-01` ★ SQLAlchemy 的 Model、Column、relationship 分别是什么？
- `D-02` ★ `Order` 为什么同时保存 `package_id`、`package_name`、`package_snapshot` 和 `contract_snapshot`？
- `D-03` ★ 订单中的 `customer_id` 和 `photographer_id` 都指向 `users.id`，如何避免 relationship 混淆？
- `D-04` ★ `SAEnum(OrderStatus)` 有什么优点？枚举变更时要注意什么？
- `D-05` ★ 为什么金额字段使用 `Numeric`，而不是 Python float？
- `D-06` ★ `CheckConstraint("currency = 'CNY'")` 的作用是什么？约束放在数据库和代码各有什么区别？
- `D-07` ★ JSON 字段适合存什么？订单的 `delivery`、`deliverables`、`contract_snapshot` 为什么可能采用 JSON？
- `D-08` ★ `cascade="all, delete-orphan"` 的含义是什么？误用会造成什么风险？

### D2. 事务、迁移与并发

- `D-09` ★ 什么是数据库事务的 ACID？本项目订单状态变更为什么必须在事务中完成？
- `D-10` ★ Alembic migration 解决了什么问题？为什么不能只修改 Model 后重启服务？
- `D-11` ★ 如果两个请求同时抢同一个摄影师档期，如何避免重复预约？
- `D-12` ★ 订单冲突检查只在 Python 查询中完成够不够？数据库层还能做什么？
- `D-13` ★ SQLAlchemy Session 的 commit、flush、refresh、rollback 分别做什么？
- `D-14` ★ 如何排查 N+1 查询？本项目 relationship 查询可能有哪些性能问题？
- `D-15` ★ SQLite 与 PostgreSQL 在并发、JSON、锁和 pgvector 支持上有什么差异？

---

## 六、板块 E：订单状态机、支付与业务一致性

### E1. 订单状态机

- `E-01` ★ 请解释 `pending`、`awaiting_customer_payment`、`confirmed`、`in_progress`、`delivered`、`received`、`reviewed`、`completed`、`cancelled` 的业务含义。
- `E-02` ★ 为什么订单状态不能由多个接口随意赋值，而要通过统一状态转换入口？
- `E-03` ★ 如何判断一个状态转换是否合法？请举例说明“摄影师接单”和“客户评价”。
- `E-04` ★ 改期申请为什么单独建表，而不是直接覆盖订单的预约时间？
- `E-05` ★ 订单主状态、支付状态、售后状态为什么要拆分？
- `E-06` ★ 什么是状态机中的前置条件、责任方、截止时间和自动动作？
- `E-07` ★ 后台过期 worker 如何处理超时支付、超时改期和超时验收？
- `E-08` ★ 如果 worker 重复执行，如何保证不会重复取消、退款或发通知？

### E2. 支付、交付与售后

- `E-09` ★ Mock 支付和真实第三方支付在回调、签名、状态同步上有什么差异？
- `E-10` ★ 支付回调为什么必须验签、幂等和记录原始事件？
- `E-11` ★ `escrow_amount`、`refunded_amount`、`settled_amount` 分别代表什么？如何保证金额不被重复结算？
- `E-12` ★ 交付、返修、验收、争议之间是什么关系？
- `E-13` ★ 客户超过验收期限未操作时，自动验收有什么业务风险？
- `E-14` ★ 如果支付成功但订单状态更新失败，如何恢复？
- `E-15` ★ 取消订单时，档期、支付、退款、通知和审计需要如何协调？

---

## 七、板块 F：前端 Vue 3 用户端

### F1. Vue 与路由

- `F-01` ★ `frontend/src/main.js` 做了哪些应用初始化？
- `F-02` ★ Vue 3 的组件、props、emits、computed、watch、生命周期分别解决什么问题？
- `F-03` ★ `frontend/src/router/index.js` 如何实现路由懒加载？懒加载的收益是什么？
- `F-04` ★ 为什么订单详情、AI 助手、作品详情等页面适合按路由拆分？
- `F-05` ★ 前端路由守卫与后端鉴权有什么区别？只做前端守卫安全吗？
- `F-06` ★ 项目如何处理返回上一页时的滚动位置？为什么这属于体验细节而不是业务逻辑？

### F2. 请求、状态与组件设计

- `F-07` ★ `frontend/src/utils/api.js` 中 Axios 请求拦截器和响应拦截器分别做了什么？
- `F-08` ★ 为什么要统一处理 401？清除 Token 后还需要做什么？
- `F-09` ★ Pinia store、composable 和组件本地 `ref` 应该如何分工？
- `F-10` ★ `useAIConversation.js` 为什么要缓存 `initializationPromise`？它解决了什么竞态问题？
- `F-11` ★ `appendMessages` 为什么要按消息 ID 去重？重复消息可能从哪里产生？
- `F-12` ★ 如何设计一个可复用的上传组件，处理大小、格式、预览、取消和失败重试？
- `F-13` ★ Element Plus 表单校验和后端 Pydantic 校验为什么都需要？
- `F-14` ★ 前端如何处理 loading、空状态、错误状态和重试，而不是只显示一个“请求失败”？

### F3. 用户业务页面

- `F-15` ★ 预约页面需要收集哪些字段？哪些字段应该由后端从真实套餐补全？
- `F-16` ★ 订单详情页如何根据状态显示不同操作按钮？这种判断应该完全写在模板中吗？
- `F-17` ★ 如何避免用户连续点击“确认支付”造成重复请求？
- `F-18` ★ 消息列表、通知列表和未读数为什么适合拆成不同的数据模型和状态？
- `F-19` ★ AI 返回的普通文本、推荐卡片、拍摄环境卡片和待确认操作，前端如何统一渲染？

---

## 八、板块 G：管理端、移动端与跨端设计

### G1. 管理端

- `G-01` ★ 管理端与用户端在权限、路由和数据范围上有什么区别？
- `G-02` ★ 管理端为什么适合使用独立的 `admin-frontend`，而不是在用户端隐藏几个按钮？
- `G-03` ★ 入驻审核、用户管理、订单管理、争议和财务页面各自需要哪些后端接口？
- `G-04` ★ 管理端的高风险操作如何增加二次确认、原因记录和审计？
- `G-05` ★ 管理端统计数据如何避免把分页列表查询结果误当成全量指标？

### G2. 移动端与 Capacitor

- `G-06` ★ `mobile-app` 与 `frontend` 都使用 Vue，为什么移动端还需要 Ionic Vue 和 Capacitor？
- `G-07` ★ 移动端路由中的 `requiresAuth` 和 `guestOnly` 如何工作？
- `G-08` ★ 移动端 API client 与用户端 Axios 封装有什么相同点和差异？
- `G-09` ★ Capacitor 如何把 Web 页面打包成 Android 应用？哪些能力需要原生插件？
- `G-10` ★ 移动端文件选择、键盘、状态栏、触感反馈等能力为什么不能只依赖浏览器 API？
- `G-11` ★ 用户端和移动端共用后端 API 时，如何处理版本、响应字段和兼容性？

---

## 九、板块 H：消息、通知、WebSocket 与缓存

### H1. 实时通信

- `H-01` ★ WebSocket 与普通 HTTP 轮询、SSE 有什么区别？本项目为什么使用 WebSocket？
- `H-02` ★ `ConnectionManager` 如何维护在线用户连接？一个用户多端同时在线时有什么问题？
- `H-03` ★ WebSocket 断线、重连、重复连接和服务重启如何处理？
- `H-04` ★ 为什么消息需要数据库持久化，不能只通过 WebSocket 推送？
- `H-05` ★ 通知 outbox worker 解决什么问题？它和直接在事务中发送通知有什么区别？
- `H-06` ★ 如何保证“订单事件已提交但通知发送失败”时最终还能送达？

### H2. Redis 与缓存

- `H-07` ★ 项目中 Redis 用于哪些场景？哪些数据不能只放 Redis？
- `H-08` ★ Redis 不可用时降级到 fakeredis 有什么好处和风险？
- `H-09` ★ 缓存穿透、击穿、雪崩分别是什么？摄影师列表查询如何防护？
- `H-10` ★ 点赞计数为什么可能使用 Redis Set/原子计数？最终数据如何和数据库一致？
- `H-11` ★ `distributed_lock` 的 token 校验为什么重要？直接 delete lock key 有什么风险？
- `H-12` ★ 缓存更新策略应该选择 Cache Aside、Write Through 还是其他方式？

---

## 十、板块 I：文件上传、对象存储与媒体处理

- `I-01` ★ 头像、作品图、视频和交付文件的上传链路分别是什么？
- `I-02` ★ 为什么定义 `StorageBackend` 协议，而不是让业务代码直接调用本地文件 API？
- `I-03` ★ Local Storage 与 S3/MinIO 的 URL、权限、生命周期和扩展性有什么差异？
- `I-04` ★ `normalize_folder` 和 `build_storage_key` 如何防止路径穿越？
- `I-05` ★ 上传文件时如何校验扩展名、MIME、实际文件内容和大小？
- `I-06` ★ 视频上传为什么需要断点续传、异步转码或状态查询？
- `I-07` ★ 文件已上传但数据库写入失败，或者数据库已写入但文件上传失败，如何清理和重试？
- `I-08` ★ 静态文件通过 `/static` 暴露有哪些安全和缓存问题？

---

## 十一、板块 J：AI Agent、Tool Calling 与 RAG

### J1. Agent 总体架构

- `J-01` ★ 本项目的 AI 功能与普通聊天机器人有什么本质区别？
- `J-02` ★ 一条 AI 消息从移动端 `AIAssistantPage` 到后端再回到前端，经过哪些步骤？
- `J-03` ★ 为什么要先保存用户消息和 Agent metadata，再执行后续流程？
- `J-04` ★ `intent classifier`、`orchestrator`、`decision service`、`tool service` 分别负责什么？
- `J-05` ★ 为什么当前架构同时保留规则路由和 LLM 决策层？
- `J-06` ★ `legacy`、`shadow`、`tool_loop` 三种路由模式分别适合什么阶段？

### J2. 意图、槽位与多轮状态

- `J-07` ★ 规则式意图识别如何识别“找摄影师”“发布企划”“预约”等意图？
- `J-08` ★ 槽位抽取中的城市、预算、风格、日期、时间和人数如何合并？
- `J-09` ★ 规则识别的优势和脆弱点是什么？什么时候需要 LLM 分类器？
- `J-10` ★ `AgentSlots`、`AgentTaskState`、`PendingToolAction` 分别保存什么？
- `J-11` ★ 为什么不能把多轮任务状态简单等同于聊天历史？
- `J-12` ★ 用户说“换一个”“第二个”“就这个”时，系统如何从历史推荐中解析真实资源 ID？
- `J-13` ★ 页面上下文（当前摄影师、作品、套餐或企划）为什么需要显式传给 Agent？

### J3. 工具安全与业务写操作

- `J-14` ★ 只读工具和写工具有什么区别？请举出本项目中的例子。
- `J-15` ★ 为什么模型不能自由编造摄影师 ID、套餐 ID 或订单 ID？
- `J-16` ★ `ToolSpec` 中的 `allowed_roles`、`proposal_only`、`requires_active_task` 有什么作用？
- `J-17` ★ 关注摄影师、发布企划、发布套餐、创建预约为什么需要确认？
- `J-18` ★ 什么是“先生成 pending action，下一轮确认后执行”？
- `J-19` ★ 工具幂等键如何防止重复确认或请求重试造成重复写入？
- `J-20` ★ `AgentActionLog` 应该记录哪些字段？为什么需要风险等级、耗时和结果？
- `J-21` ★ 如果模型选择了未注册工具、越权工具或参数不合法，后端如何拒绝？

### J4. RAG 与多模态检索

- `J-22` ★ RAG 在这个项目中解决什么问题？为什么不能只让模型根据 Prompt 推荐摄影师？
- `J-23` ★ `AIResourceDocument` 如何统一索引摄影师、作品和套餐？
- `J-24` ★ 混合检索中的语义分、关键词分、业务分、质量分和新鲜度分如何组合？
- `J-25` ★ 城市、预算、风格、化妆和套餐内容哪些适合硬过滤，哪些适合软排序？
- `J-26` ★ 为什么检索结果需要带 `references` 和允许引用的资源 ID？
- `J-27` ★ 空结果时如何防止模型编造不存在的推荐？
- `J-28` ★ 图片驱动检索如何从视觉特征进入图片向量和文本向量排序？
- `J-29` ★ SQLite JSON 向量和 PostgreSQL pgvector 在检索实现上有什么差异？

### J5. Provider、降级与评测

- `J-30` ★ `AIProvider` 抽象解决了什么问题？Mock Provider 对测试有什么价值？
- `J-31` ★ 主模型超时、返回非法 JSON、视觉模型失败时，系统如何 fallback？
- `J-32` ★ Prompt、Orchestrator、Index、Tool Schema 为什么需要分别版本化？
- `J-33` ★ AgentTrace、AgentActionLog、AgentRetrievalLog 分别回答什么排障问题？
- `J-34` ★ Golden JSONL 离线评测如何评估意图分类、工具选择和检索质量？
- `J-35` ★ 如何衡量 Agent 灰度上线是否成功？请设计至少 5 个指标。

---

## 十二、板块 K：测试、质量与可观测性

### K1. 测试策略

- `K-01` ★ 单元测试、接口测试、集成测试和 Playwright E2E 测试分别验证什么？
- `K-02` ★ `backend/tests/conftest.py` 为什么使用内存 SQLite、StaticPool 和依赖覆盖？
- `K-03` ★ 测试中为什么要每个用例创建/删除表并清空 Redis？
- `K-04` ★ 如何测试需要登录、角色权限和订单参与者身份的接口？
- `K-05` ★ 如何测试时间相关逻辑，例如支付过期、改期过期、自动验收？
- `K-06` ★ Mock 支付、Mock AI、fakeredis 会不会让测试失去价值？如何补充真实集成测试？
- `K-07` ★ 前端 Vitest 与 Playwright 各适合测试哪些内容？
- `K-08` ★ 你会优先阅读哪些测试来理解项目设计？为什么？

### K2. 质量与排障

- `K-09` ★ 线上出现“订单已支付但页面仍显示未支付”，你会如何定位？
- `K-10` ★ 线上出现“用户收到两条相同通知”，你会检查哪些地方？
- `K-11` ★ AI 推荐了不存在的摄影师，你会从分类、检索、引用和生成哪几层排查？
- `K-12` ★ 你会如何设计结构化日志、trace_id 和请求耗时指标？
- `K-13` ★ 如何区分数据库慢、外部模型慢、Redis 慢和前端渲染慢？

---

## 十三、板块 L：部署、性能与生产化

- `L-01` ★ Docker Compose 中各服务的依赖关系和健康检查有什么作用？
- `L-02` ★ 为什么生产环境不能使用默认 `SECRET_KEY`、数据库密码和 MinIO 密钥？
- `L-03` ★ 本地 SQLite 迁移到 PostgreSQL 需要注意哪些兼容性问题？
- `L-04` ★ FastAPI 多 worker 部署时，全局 WebSocket manager 和后台 worker 会有什么问题？
- `L-05` ★ 如何把后台过期任务、outbox worker 和 AI 索引 worker 从 API 进程中拆出去？
- `L-06` ★ 摄影师列表、作品列表和推荐接口如何做索引、缓存和分页优化？
- `L-07` ★ AI 请求串行调用分类、检索、视觉模型和生成模型时，如何降低端到端延迟？
- `L-08` ★ 大文件上传、图片向量化和视频处理如何异步化？
- `L-09` ★ 如何设计限流、熔断、重试和超时，避免外部 AI Provider 拖垮 API？
- `L-10` ★ 如果系统流量增长 10 倍，你会优先改哪三个地方？为什么？

---

## 十四、板块 M：架构设计与开放题

- `M-01` ★ 如果新增“申请企划”工具，需要修改哪些契约、权限、状态、日志和测试？
- `M-02` ★ 如果要支持多人摄影师协作订单，现有订单模型和状态机如何演进？
- `M-03` ★ 如果支付从 Mock 接入真实微信/支付宝，哪些模块需要抽象？
- `M-04` ★ 如果要支持多币种，当前 CNY 数据库约束和金额模型如何改造？
- `M-05` ★ 如果用户要求删除账号，订单、消息、评价、审计日志和 AI 对话如何处理？
- `M-06` ★ 如果一个用户同时打开 Web、移动端和多个浏览器标签页，如何保证会话、消息和未读数一致？
- `M-07` ★ 你认为当前 `ai_service.py` 过大的主要问题是什么？如何拆分而不破坏现有行为？
- `M-08` ★ 任务状态放在消息 metadata 中有什么优点和缺点？什么时候应迁移到独立任务表？
- `M-09` ★ 你会如何定义“推荐质量”和“预约转化率”，避免只看模型准确率？
- `M-10` ★ 如果重新设计这个项目，你会保留什么、重构什么、删除什么？

---

## 十五、板块 N：项目经历与面试表达

- `N-01` ★ 请用 STAR 方法讲一个你在项目中解决的复杂问题。
- `N-02` ★ 这个项目最难的技术问题是什么？为什么难？
- `N-03` ★ 你做过哪些安全性设计？请不要只回答“用了 JWT”。
- `N-04` ★ 你如何证明订单状态机设计是可靠的？
- `N-05` ★ 你如何证明 AI Agent 没有直接变成一个会编造数据的聊天机器人？
- `N-06` ★ 如果面试官质疑项目中的支付和 AI 都是 Mock，你如何诚实且有说服力地回答？
- `N-07` ★ 项目当前有哪些技术债？你会如何安排治理优先级？
- `N-08` ★ 请用 30 秒、1 分钟和 3 分钟三个版本介绍本项目。

---

## 十六、推荐代码阅读入口

### 后端

- [backend/app/main.py](../backend/app/main.py)：应用装配、生命周期、路由和中间件
- [backend/app/api/deps.py](../backend/app/api/deps.py)：数据库依赖与认证依赖
- [backend/app/core/security.py](../backend/app/core/security.py)：密码、JWT、验证码 Token
- [backend/app/core/config.py](../backend/app/core/config.py)：环境配置和能力开关
- [backend/app/models/order.py](../backend/app/models/order.py)：订单模型与状态枚举
- [backend/app/services/order_service.py](../backend/app/services/order_service.py)：订单状态机、事件和后台过期任务
- [backend/app/services/ai_orchestrator_service.py](../backend/app/services/ai_orchestrator_service.py)：规则意图与槽位提取
- [backend/app/services/ai_agent_tool_service.py](../backend/app/services/ai_agent_tool_service.py)：写工具、确认、幂等和 ActionLog
- [backend/app/core/cache.py](../backend/app/core/cache.py)：Redis、fakeredis、缓存和分布式锁
- [backend/app/services/ws_manager.py](../backend/app/services/ws_manager.py)：WebSocket 连接管理

### 前端与移动端

- [frontend/src/router/index.js](../frontend/src/router/index.js)：用户端路由
- [frontend/src/utils/api.js](../frontend/src/utils/api.js)：用户端 Axios 封装
- [frontend/src/composables/useAIConversation.js](../frontend/src/composables/useAIConversation.js)：AI 会话状态
- [admin-frontend/src/router/index.js](../admin-frontend/src/router/index.js)：管理端路由
- [mobile-app/src/api/client.ts](../mobile-app/src/api/client.ts)：移动端 API 客户端
- [mobile-app/src/router/index.ts](../mobile-app/src/router/index.ts)：移动端鉴权路由
- [mobile-app/src/pages/AIAssistantPage.vue](../mobile-app/src/pages/AIAssistantPage.vue)：移动端 AI 交互入口

### 测试与部署

- [backend/tests/conftest.py](../backend/tests/conftest.py)：后端测试环境和 Fixtures
- [backend/tests/test_order_service.py](../backend/tests/test_order_service.py)：订单业务测试
- [backend/tests/test_ai_api.py](../backend/tests/test_ai_api.py)：AI API 测试
- [backend/tests/test_ai_phase_c_rollout.py](../backend/tests/test_ai_phase_c_rollout.py)：Agent 灰度测试
- [docker-compose.yml](../docker-compose.yml)：生产依赖服务编排
- [README.md](../README.md)：启动、测试、部署和业务主线

## 十七、建议面试顺序

1. `A-01`～`A-15`：确认基础概念和项目全景。
2. `B-01`～`C-14`：确认后端分层、鉴权和安全意识。
3. `D-01`～`E-15`：确认数据库建模和核心订单业务能力。
4. `F-01`～`I-08`：确认前端、跨端、实时通信和文件处理能力。
5. `J-01`～`J-35`：深入 AI Agent、Tool Calling、RAG 和生产化。
6. `K-01`～`L-10`：确认测试、排障、部署和性能能力。
7. `M-01`～`N-08`：进行架构开放题和项目经历表达。

建议第一轮先完成 `A`～`E`，建立系统与订单主线；第二轮再进入 `J`，避免只会讲 AI 名词而讲不清真实业务链路。
