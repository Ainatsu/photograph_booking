# 阶段三：学习项目相关“八股”

## 一、阶段目标

本阶段不是脱离项目背诵面试题，而是把项目中的实现转化为可以解释、可以追问、可以复现的工程知识。

最终应当能够围绕摄影师预约平台回答四类问题：

1. 这个技术是什么，解决什么问题？
2. 项目中哪里使用了它，请说明完整调用链。
3. 为什么采用当前方案？它的限制和风险是什么？
4. 如果流量、数据量或安全要求提高，如何改进？

推荐的学习闭环：

```text
知识点
  -> 项目代码位置
  -> 一条真实请求的调用链
  -> 设计原因和替代方案
  -> 测试或小功能验证
  -> 用自己的话回答连续追问
```

本阶段不要求背下所有框架 API。优先掌握和简历、项目、目标岗位直接相关的内容，并能诚实区分“项目已经实现”“项目可以改进”和“自己还没有验证”。

## 二、项目知识地图

### 2.1 传统后端主线

```text
前端请求
  -> FastAPI Router
  -> Depends 认证/数据库依赖
  -> Pydantic 校验
  -> Service 业务规则
  -> SQLAlchemy Model / Redis / 文件存储
  -> 数据库事务提交
  -> Response Schema
```

### 2.2 预约业务主线

```text
浏览摄影师/套餐
  -> 查询可预约资源
  -> 创建订单
  -> 摄影师接单或拒单
  -> 支付
  -> 拍摄交付
  -> 客户验收
  -> 评价或争议处理
```

### 2.3 Agent 主线

```text
用户消息
  -> 会话与消息持久化
  -> 意图/槽位识别
  -> 决策与工具授权
  -> 检索或业务工具
  -> 任务状态更新
  -> 写操作确认与幂等执行
  -> 结构化结果、引用和审计日志
```

## 三、学习方法与记录模板

每个知识点至少记录以下内容：

```markdown
### 知识点：

- 一句话定义：
- 项目文件：
- 请求调用链：
- 为什么这样设计：
- 当前方案缺点：
- 可选改进：
- 我能写出的测试：
- 面试回答：
```

建议每章形成一张“项目八股卡片”。回答时先讲结论，再讲项目证据，最后讲边界和改进，不要只说概念定义。

## 四、Python 基础与进阶

### 4.1 必学目录

- 基本数据结构：`list`、`dict`、`set`、`tuple` 的特点、复杂度和使用场景
- 可变对象与不可变对象、浅拷贝与深拷贝
- 函数参数、默认参数、可变参数、闭包和装饰器
- 迭代器、生成器、列表推导式和惰性计算
- 类、继承、组合、抽象接口和协议式设计
- 异常类型、异常链、资源清理和上下文管理器
- 类型注解、`Optional`、泛型、`dataclass` 与 Pydantic 的边界
- 模块导入、循环依赖、配置读取和日志基础
- 时间、时区、字符串编码、JSON 序列化
- 基础算法：哈希表、双指针、二分查找、栈队列、排序和复杂度分析

### 4.2 项目落点

- `backend/app/core/security.py`：密码哈希、JWT、HMAC、异常处理
- `backend/app/core/cache.py`：装饰器、上下文管理器、同步/异步包装
- `backend/app/core/timezone.py`：日期、时间和时区处理
- `backend/app/services/ai_agent_contracts.py`：类型约束和结构化数据契约
- `backend/app/services/ai_provider.py`：Provider 协议与实现替换

### 4.3 面试必须讲清楚

- 为什么密码不能直接保存，bcrypt 和普通哈希有什么区别？
- 装饰器如何保留原函数信息？同步函数和异步函数为什么要分别包装？
- 生成器什么时候有价值？它是否能自动解决内存和并发问题？
- `dict` 平均查找为什么是 O(1)，最坏情况是什么？
- 为什么项目中需要类型注解？类型注解是否等于运行时校验？
- 异常应该在哪里捕获？为什么不能在所有地方都用 `except Exception`？

### 4.4 练习与验收

1. 不看项目，写一个带 TTL 的内存缓存装饰器。
2. 写一个读取 JSON 文件并校验字段的函数，处理文件不存在、格式错误和字段缺失。
3. 用一个字典实现订单状态统计，说明时间复杂度。
4. 解释 `backend/app/core/cache.py` 中 `distributed_lock` 的进入、释放和异常路径。

## 五、FastAPI、Pydantic 与依赖注入

### 5.1 必学目录

- ASGI、Uvicorn、路由、请求生命周期和响应模型
- Path、Query、Header、Cookie、Body 参数的来源和校验
- Pydantic 模型、嵌套模型、默认值、枚举、字段约束和自定义校验
- `Depends` 的依赖注入、依赖复用和依赖覆盖测试
- `Session` 数据库依赖的创建、使用和关闭
- 认证依赖、角色依赖和可选用户依赖
- HTTP 异常、统一错误结构、状态码和响应序列化
- CORS、文件上传、WebSocket 和后台任务的基本边界
- Router、Schema、Service、Model 的职责划分

### 5.2 项目落点

- `backend/app/main.py`：应用装配和路由注册
- `backend/app/api/deps.py`：当前用户、活跃用户和数据库依赖
- `backend/app/api/v1/ai.py`、`orders.py`、`users.py`：接口入口
- `backend/app/schemas/`：请求和响应数据契约
- `backend/tests/test_auth_dependencies.py`：依赖和认证测试

### 5.3 面试必须讲清楚

- 一次 `POST /api/v1/...` 请求如何经过 Router、依赖、Schema 和 Service？
- 为什么不能直接在 Router 中写所有数据库和业务逻辑？
- `Depends` 是不是简单的全局变量？如何在测试中替换依赖？
- Pydantic 校验和数据库约束分别保护哪一层？为什么两者都需要？
- 为什么响应模型不能直接暴露 ORM 对象的全部字段？
- 同步 SQLAlchemy Session 放在 `async def` 中有什么性能风险？

### 5.4 练习与验收

1. 独立写一个“查询可预约套餐”的 FastAPI 接口，包含 Query 校验、当前用户可选认证和响应模型。
2. 为一个订单接口补充参数错误、未登录、无权限和资源不存在四类测试。
3. 画出“登录接口”和“创建订单接口”的依赖调用链。

## 六、HTTP、RESTful API 与 WebSocket

### 6.1 必学目录

- HTTP 请求报文：方法、URL、Header、Body 和状态码
- GET、POST、PUT、PATCH、DELETE 的语义和幂等性
- 2xx、3xx、4xx、5xx 的常见使用场景
- JSON、文件上传、分页、筛选、排序和错误响应
- REST 资源建模、URL 版本化和兼容性
- Cookie、Bearer Token、CORS、缓存控制和超时
- WebSocket 握手、连接管理、广播、断线和重连
- 接口超时、重试和重复请求之间的关系

### 6.2 项目落点

- `backend/app/api/v1/`：版本化 API 路由
- `backend/app/api/v1/ws.py` 与 `backend/app/services/ws_manager.py`：实时消息
- `backend/app/api/v1/ai.py`：会话消息、附件和结构化 Agent 响应
- `mobile-app/src/api/`：前端请求封装和错误处理

### 6.3 高频追问

- 创建订单应该使用 POST 还是 PUT？为什么？
- 支付回调重复到达时，HTTP 方法的幂等性是否足够？
- WebSocket 断线后，如何保证用户不会永久漏掉通知？
- 为什么实时推送不能替代数据库中的消息和未读状态？
- 服务器返回 401、403、404、409、422 时，客户端应如何区分？
- AI 请求为什么可能需要较长超时？超时后客户端重试会带来什么问题？

### 6.4 练习与验收

写一份订单 API 设计表，至少包含：路径、方法、请求字段、成功响应、错误状态码、是否需要登录、是否幂等。再为 WebSocket 设计“连接、推送、重连、补拉未读消息”的流程。

## 七、JWT、认证与授权

### 7.1 必学目录

- 密码哈希、盐、验证和密码长度限制
- JWT 的 Header、Payload、Signature、`iat`、`exp` 和 `sub`
- Bearer Token 的携带方式与令牌泄露风险
- 认证 Authentication 与授权 Authorization 的区别
- 用户身份、账号状态、角色和资源所有权校验
- Access Token、Refresh Token、撤销和轮换
- `token_version` 让旧 Token 失效的原理
- JWT 不适合保存密码、验证码和高敏感业务数据的原因
- CSRF、XSS、日志脱敏和 HTTPS 的基本安全要求

### 7.2 项目落点

- `backend/app/core/security.py`：bcrypt、JWT、验证码哈希
- `backend/app/api/deps.py`：解析 Token、查询用户、校验版本和活跃状态
- `backend/app/models/user.py`：角色、状态和 `token_version`
- `backend/tests/test_security.py`、`test_auth_dependencies.py`：安全边界

### 7.3 必须能回答

- 登录成功后，前端如何携带 JWT？后端如何得到当前用户？
- JWT 签名能防止什么，不能防止什么？Payload 是否加密？
- 修改密码或强制下线后，旧 Token 为什么还能被拒绝？
- 仅校验“已登录”为什么不足以访问摄影师管理接口？
- 为什么“用户拥有这个资源”不能只依赖模型传入的 ID？

### 7.4 练习与验收

手工画出从登录到创建订单的认证流程，并标出每个可能失败点：Token 缺失、签名错误、过期、用户不存在、版本不一致、账号禁用、角色不允许、资源不属于当前用户。

## 八、SQL、索引、事务与数据一致性

### 8.1 必学目录

- 表、主键、外键、唯一约束、非空约束和检查约束
- 一对一、一对多、多对多关系
- `JOIN`、聚合、子查询、分页和排序
- B+Tree 索引、联合索引、最左匹配、选择性和回表
- `EXPLAIN` 的基本阅读方式
- 事务的原子性、一致性、隔离性、持久性
- 脏读、不可重复读、幻读和常见隔离级别
- 提交、回滚、锁等待、死锁和长事务
- 数据库约束与应用层校验的互补关系
- 状态机、事件表、软删除和审计数据

### 8.2 项目落点

- `backend/app/models/order.py`、`order_event.py`、`order_reschedule.py`、`payment.py`
- `backend/app/models/ai_conversation.py`、`agent_task.py`、`ai_resource.py`
- `backend/app/services/order_service.py`、`payment_service.py`、`availability_service.py`
- `backend/tests/test_order_service.py`、`test_payment_service.py`、`test_availability_service.py`

### 8.3 预约项目重点

- 创建订单前为什么要再次检查摄影师档期？
- 接单时为什么不能只修改 `order.status`？还需要检查哪些状态、角色和时间条件？
- 改期申请为什么不能直接覆盖原时间？批准、拒绝、过期分别怎样处理？
- 支付记录为什么要有独立状态和业务单号？
- 订单事件表解决了什么问题？它与当前状态字段是什么关系？

### 8.4 必须掌握的并发思路

```text
请求 A：检查时间空闲 -> 请求 B：检查时间空闲
请求 A：创建订单     -> 请求 B：创建订单
```

如果只有“先查询、后写入”，两个请求都可能通过检查。可选防护包括数据库唯一约束、事务锁、条件更新、短期分布式锁和失败重试。面试时要说明锁不是万能的，最终一致性仍需要数据库约束或状态校验兜底。

### 8.5 练习与验收

1. 写 SQL 查询某摄影师在日期范围内的订单和冲突时间。
2. 使用 `EXPLAIN` 比较有无索引的查询计划。
3. 设计一个订单状态流转图，标出允许和禁止的跳转。
4. 设计两个并发创建订单的测试，并说明如何证明没有重复预约。

## 九、SQLAlchemy、N+1 与 Alembic

### 9.1 必学目录

- Engine、Session、事务和 ORM 映射
- Query、过滤、排序、分页和批量操作
- relationship、lazy loading、joinedload 和 selectinload
- N+1 查询的识别、影响和修复
- flush、commit、refresh、rollback 的区别
- 事务中异常后的 Session 状态
- DTO/Schema 与 ORM Model 的转换
- Alembic revision、upgrade、downgrade 和数据迁移
- 生产迁移中的锁表、默认值、回滚和兼容发布

### 9.2 项目落点

- `backend/app/core/database.py`
- `backend/app/models/`
- `backend/migrations/`
- 各业务 Service 中的 Session 使用方式
- `backend/tests/test_migration_user_email_nullable.py`

### 9.3 高频追问

- 为什么不能把数据库 Session 当作全局单例？
- `commit()` 后为什么有时还要 `refresh()`？
- 查询订单列表时如何避免每条订单再次查询用户、套餐和摄影师？
- Alembic 自动生成迁移是否一定正确？JSON 字段改结构如何保护已有数据？
- 数据库迁移和代码发布的先后顺序如何安排？

### 9.4 练习与验收

用 SQLAlchemy 写一个带分页和关联预加载的订单查询；打开 SQL 日志，确认不会产生明显的 N+1。再为一个新增可空字段编写迁移和回滚方案。

## 十、Redis、缓存一致性与分布式锁

### 10.1 必学目录

- Redis 的 String、Hash、List、Set、Sorted Set
- TTL、过期、淘汰、持久化和内存风险
- Cache Aside：读缓存、回源、写库、删缓存
- 缓存穿透、击穿、雪崩和热点 Key
- 缓存 Key 设计、版本号、租户/用户隔离和序列化
- Redis 原子命令与计数场景
- `SET NX EX` 分布式锁、唯一 token 和安全释放
- 锁过期、业务超时、续期、误删锁和锁粒度
- Redis 不可用时的降级边界

### 10.2 项目落点

- `backend/app/core/cache.py`：缓存、fakeredis 降级、计数和锁
- `backend/app/core/config.py`：Redis 配置
- 点赞、推荐、可用性和查询服务中的缓存使用
- `backend/tests/test_cache.py`

### 10.3 高频追问

- 为什么缓存更新常采用“写数据库后删除缓存”，而不是先更新缓存？
- 数据库写成功但删除缓存失败怎么办？
- 项目的 fakeredis 降级能否用于多进程生产环境？为什么？
- 分布式锁过期但业务还没完成时会发生什么？如何降低风险？
- 只使用 Redis 锁能否保证订单不重复？为什么还需要数据库约束？

### 10.4 练习与验收

实现一个查询缓存，并补充命中、未命中、过期、缓存不可用和数据更新后的失效测试。画出“缓存、数据库、锁、请求”之间的时序图。

## 十一、并发、异步、线程与进程

### 11.1 必学目录

- I/O 密集与 CPU 密集
- Python GIL 的影响和常见误解
- `asyncio`、协程、事件循环和 `await`
- 同步阻塞函数放入异步接口的风险
- 线程池、进程池和多 Worker
- 共享内存、竞态条件、锁、信号量和队列
- 数据库连接池、HTTP 客户端连接池和超时
- 重试、退避、限流、熔断和任务取消

### 11.2 项目落点

- FastAPI 的同步/异步接口与数据库访问
- `backend/app/core/cache.py` 的同步/异步缓存包装
- AI Provider、天气、地理编码等外部 I/O
- WebSocket 连接管理和消息推送
- 订单档期检查、支付和 Agent 工具执行

### 11.3 高频追问

- `async def` 中调用同步数据库查询会不会自动异步？
- 多个请求同时修改同一订单时，应用锁和数据库锁分别保护什么？
- 外部模型调用超时，如何避免整个请求一直占用资源？
- 多进程部署后，内存字典锁为什么失效？
- 重试是否一定安全？哪些写操作必须带幂等键？

### 11.4 练习与验收

1. 写一个带超时和指数退避的异步 HTTP 调用。
2. 用两个并发任务模拟重复支付或重复创建订单。
3. 说明单进程 fakeredis、真实 Redis 和数据库约束在不同部署模式下的差异。

## 十二、Docker、Linux 与部署

### 12.1 必学目录

- 镜像、容器、Volume、Network、Port 和环境变量
- Dockerfile 的基础镜像、依赖安装、启动命令和健康检查
- `docker-compose.yml` 中服务依赖、配置和数据持久化
- PostgreSQL、Redis、MinIO 的职责和连接方式
- 本地 SQLite 与生产 PostgreSQL 的差别
- Linux 进程、端口、日志、权限、磁盘和环境变量
- 反向代理、静态文件、CORS 和 HTTPS 基础
- 数据库备份、迁移、回滚和部署顺序

### 12.2 项目落点

- `docker-compose.yml`
- `backend/Dockerfile`
- `admin-frontend/Dockerfile`、`admin-frontend/nginx.conf`
- `.env.example`、`backend/app/core/config.py`
- `backend/storage/` 与 `backend/app/storage/`

### 12.3 高频追问

- 为什么本地 SQLite 能运行，生产仍建议 PostgreSQL？
- 容器删除后，数据库和上传文件为什么不能跟着丢？
- Docker Compose 中 Redis、MinIO 和后端如何通过服务名通信？
- 配置为什么不能写死在代码里？哪些配置不能提交 Git？
- 迁移失败时如何判断是代码问题、连接问题还是数据问题？

### 12.4 练习与验收

不看启动脚本，独立说明项目启动所需服务、端口、环境变量和数据目录；再模拟一次“后端连接不上 Redis”的排查路径。

## 十三、Git、测试、日志与可观测性

### 13.1 必学目录

- Git commit、branch、merge、rebase、冲突处理和回滚思路
- 单元测试、集成测试、接口测试、端到端测试的边界
- pytest fixture、参数化、mock、依赖覆盖和测试数据库
- 正常路径、边界、权限、并发、外部服务失败和回滚测试
- 日志级别、结构化字段、Trace ID、用户数据脱敏
- 指标：吞吐量、错误率、延迟、缓存命中率、任务成功率
- AI 特有指标：检索命中、引用正确率、工具选择准确率、幻觉率、Token 成本

### 13.2 项目落点

- `backend/tests/`：业务、认证、缓存、Agent 和回归测试
- `backend/app/services/ai_observability_service.py`
- `backend/app/services/ai_trace_service.py`
- `backend/app/models/ai_conversation.py`：Agent 操作和检索日志
- `backend/scripts/evaluate_ai_agent.py`、`evaluate_hybrid_rag.py`

### 13.3 高频追问

- 你如何证明创建订单没有时间冲突？
- 为什么测试不能只测 200 响应？
- 外部模型不可用时如何测试 fallback，而不依赖真实 API？
- 日志中能不能记录完整 Token、手机号、Authorization 和模型输入？
- Agent 的“效果好”如何定义和量化？

### 13.4 练习与验收

为“创建预约”补齐一组测试矩阵：成功、字段缺失、资源不存在、权限不足、时间冲突、重复请求、事务失败、通知失败。每项写出断言和测试替身。

## 十四、RAG、Embedding 与向量检索

### 14.1 必学目录

- RAG 与普通聊天、微调的区别
- 文档切分、清洗、元数据、Embedding 和向量相似度
- 关键词检索、向量检索和混合检索
- 结构化过滤：城市、预算、风格、资源类型和可预约状态
- 召回、排序、阈值、Top-K 和重复结果
- 向量索引更新、内容哈希、版本化和失败重试
- 引用、来源、空结果和防止模型编造
- 评估集、Recall、Precision、MRR、引用正确率和人工评估
- 多模态 RAG：图片特征、文本特征和联合排序

### 14.2 项目落点

- `backend/app/models/ai_resource.py`：统一资源文档
- `backend/app/services/ai_resource_index_service.py`
- `backend/app/services/ai_embedding_service.py`
- `backend/app/services/ai_retrieval_service.py`
- `backend/app/services/ai_search_tool_service.py`
- `backend/scripts/evaluate_hybrid_rag.py`、`evaluate_multimodal_rag.py`

### 14.3 高频追问

- 为什么项目不能让模型直接凭记忆推荐摄影师和套餐？
- 预算和城市这类条件为什么要做结构化过滤，而不只靠向量相似度？
- 关键词分、向量分、业务质量分如何组合？权重如何验证？
- 资源更新后如何判断是否需要重新 Embedding？
- 检索为空时为什么不能让模型“给几个可能的结果”？
- 如何证明回答引用的资源确实来自检索结果？

### 14.4 练习与验收

用 10 条真实或脱敏资源构造一个小型评估集，分别测试关键词检索、向量检索和混合检索，记录 Top-K、命中率、错误推荐和空结果行为。

## 十五、Tool Calling、Agent 状态与业务安全

### 15.1 必学目录

- 普通聊天、RAG、Workflow 和 Agent 的边界
- 意图识别、槽位提取、路由、Planner 和工具执行
- 工具注册、参数 Schema、工具别名和工具结果结构
- 只读工具、可逆写操作、敏感写操作和禁止操作
- 角色权限、资源所有权、任务前置条件和服务端二次校验
- 多轮任务状态、草稿、版本号、revision 和过期状态
- 待确认动作、确认/取消/修改和重新确认
- 幂等键、重复调用、重试和补偿
- Action Log、Trace、错误码、延迟和成本
- Prompt Injection、越权工具调用、敏感信息泄露和输出约束

### 15.2 项目落点

- `backend/app/services/ai_intent_classifier_service.py`
- `backend/app/services/ai_agent_decision_service.py`
- `backend/app/services/ai_tool_policy_service.py`
- `backend/app/services/ai_agent_tool_service.py`
- `backend/app/services/agent_task_service.py`
- `backend/app/services/ai_search_context_service.py`
- `backend/app/models/agent_task.py`、`ai_conversation.py`
- `backend/tests/test_ai_phase_a_routing.py`、`test_ai_phase_b_tool_routing.py`、`test_agent_form_task_service.py`

### 15.3 必须能回答

- 为什么模型选中了工具，后端仍不能直接执行？
- 为什么实体 ID 必须来自真实检索结果、页面上下文或服务端查询？
- 创建订单、发布套餐、关注摄影师为什么要确认，而搜索可以直接执行？
- 一个确认请求重复到达时，如何保证只写入一次？
- Agent 状态放在聊天历史、数据库草稿还是 Redis 中，各有什么取舍？
- 如何防止用户通过提示词绕过角色权限或调用隐藏工具？
- Tool Calling 失败时，怎样返回可恢复的任务状态，而不是只说“系统错误”？

### 15.4 练习与验收

1. 设计一个 `create_booking` 工具 Schema，禁止模型直接传入任意用户 ID 和订单 ID。
2. 画出“用户说确认”到订单落库的时序图，标出授权、幂等、事务和日志。
3. 为工具调用写四类测试：未注册工具、参数非法、角色不允许、重复幂等键。
4. 解释 `READ_ONLY`、`REVERSIBLE_WRITE`、`SENSITIVE_WRITE` 的差异。

## 十六、大模型接入、幻觉、评估与生产化

### 16.1 必学目录

- Provider 抽象、模型选择、文本模型与视觉模型
- Prompt 的系统指令、上下文、输出格式和版本化
- temperature、Token、上下文窗口、超时和成本
- JSON 输出清洗、Schema 校验和非法结果回退
- 主 Provider、备用 Provider、规则回退和功能降级
- 上下文裁剪、历史消息、页面上下文和隐式引用
- 幻觉来源：知识缺失、检索错误、提示冲突、上下文过长
- 离线评估、回归集、线上抽样和人工复核
- 延迟、费用、成功率、拒答率和用户完成率

### 16.2 项目落点

- `backend/app/services/ai_provider.py`
- `backend/app/services/ai_intent_prompt.py`
- `backend/app/services/ai_agent_decision_prompt.py`
- `backend/app/services/ai_evaluation_service.py`
- `backend/app/services/ai_offline_eval_service.py`
- `backend/app/core/config.py` 中 Provider、Embedding 和 Agent 路由配置

### 16.3 高频追问

- 模型返回非法 JSON 时怎么办？为什么不能直接 `json.loads` 后报错？
- 规则路由、LLM 路由和 hybrid 路由各适合什么阶段？
- 为什么 Mock Provider 对 Agent 测试很重要？
- 如何判断一次 Agent 失败是分类错、检索错、工具错还是模型生成错？
- 如何降低 Token 成本而不破坏任务状态？
- Prompt Injection 能否仅靠系统 Prompt 解决？

### 16.4 练习与验收

给一个意图分类器设计 fallback 矩阵：模型超时、空内容、非法 JSON、未知意图、低置信度、规则与模型冲突。每种情况写出路由、日志字段和用户可见结果。

## 十七、项目综合追问目录

以下问题要按照“结论 → 代码位置 → 调用链 → 取舍 → 缺点/改进”的顺序练习。

### 17.1 项目总览

- 项目解决了什么问题？服务哪些角色？
- 前端、后端、数据库、Redis、对象存储和 AI 模块分别负责什么？
- 你负责的边界是什么？哪部分是后来改造的？
- 最复杂的一条业务链路是什么？为什么复杂？

### 17.2 预约与支付

- 创建订单如何校验套餐、摄影师、日期、时长和用户权限？
- 如何避免同一档期重复预约？数据库约束和锁分别做什么？
- 订单状态为什么不能任意修改？如何记录状态变更？
- 支付重复回调如何处理？支付成功但通知失败怎么办？
- 改期申请为什么要单独建模？批准后如何重新检查档期？

### 17.3 消息与交付

- WebSocket 断线后如何补消息？
- 未读数为什么需要持久化或可重建？
- 文件上传如何限制类型、大小和访问权限？
- MinIO/S3 和本地存储如何切换？
- 交付、验收、评价和争议之间有什么状态约束？

### 17.4 Agent 与 RAG

- 用户说“帮我找一个成都婚礼摄影师”，请求经过哪些阶段？
- 用户说“就第二个”，系统如何知道“第二个”指什么？
- 为什么搜索结果必须有 references？
- 用户说“确认发布”，系统如何确认他确认的是哪个动作？
- 如何防止 Agent 代替用户执行高风险操作？
- Agent 与传统 Service 的边界在哪里？

### 17.5 工程质量

- 你写过的最有价值的测试是什么？
- 测试如何替代真实模型和外部支付服务？
- 线上出现接口变慢，你先看哪些日志和指标？
- 你发现项目当前方案的一个缺点是什么？如何改进？

## 十八、四周学习安排

### 第 1 周：Python、FastAPI、HTTP、认证

- 学习第四至第七章
- 复现登录、当前用户依赖和一个订单查询接口
- 手写 2 道基础算法题、1 个 FastAPI 接口、1 组认证测试
- 完成“登录到创建订单”的调用链图

### 第 2 周：SQL、SQLAlchemy、事务、Redis、并发

- 学习第八至第十一章
- 重点阅读订单、支付、档期、缓存和测试代码
- 写一个并发重复预约测试和一个缓存失效测试
- 完成订单状态机、事务边界和分布式锁时序图

### 第 3 周：Docker、测试、日志、RAG

- 学习第十二至第十四章
- 跑通本地测试和 AI 检索评估脚本
- 解释 Compose 中各服务的职责和故障表现
- 对一个资源搜索流程完成“检索输入、候选、排序、引用、空结果”复盘

### 第 4 周：Agent 与综合追问

- 学习第十五至第十七章
- 重点复现工具授权、待确认动作、幂等键和 Action Log
- 每天进行一次 20 分钟项目讲解和一次连续追问
- 完成第十八章的所有验收项，整理不会回答的问题

## 十九、编码练习清单

### Python

- LRU 或 TTL 缓存
- 订单状态统计
- 日志文件解析与错误汇总
- 二分查找、哈希表、区间重叠判断
- 带超时的异步请求

### SQL

- 查询摄影师在日期范围内的订单
- 查询用户未读消息数
- 查询每位摄影师的订单统计
- 使用唯一约束或条件更新避免重复写入
- 设计订单状态事件查询

### FastAPI

- 注册/登录接口
- 当前用户依赖
- 分页查询接口
- 文件上传接口
- 带 Pydantic Schema 的订单创建接口

### AI 应用

- JSON 输出清洗和 Pydantic 校验
- 规则意图分类器
- 简单工具注册器
- 待确认动作状态机
- 幂等执行器
- 基于候选 ID 的引用约束

每个练习都要补至少一个失败测试，不要只实现成功路径。

## 二十、阶段完成标准

达到以下标准，才算完成阶段三：

- 能在 3 分钟内说明项目目标、角色、架构和核心业务链路
- 能指出登录、下单、支付、消息、RAG、Tool Calling 的关键文件
- 能解释 JWT、索引、事务、缓存、异步、Docker 和测试，而不是只给定义
- 能回答“为什么这样设计、缺点是什么、如何改进”
- 能写出基础 Python、SQL、FastAPI 和结构化 LLM 调用代码
- 能说明订单并发、支付幂等和 Agent 写操作确认的风险控制
- 能解释检索为空、模型超时、工具失败和数据库回滚时的系统行为
- 能独立补一个小功能，并为正常、异常、权限和重复请求编写测试
- 对不会或未验证的内容能够明确说出边界，不虚构项目实现

## 二十一、最终复习顺序

```text
项目总览
  -> 登录鉴权
  -> 一条订单业务链路
  -> SQL/事务/并发
  -> Redis/部署/测试
  -> RAG
  -> Tool Calling 与 Agent 状态
  -> 模拟面试与编码题
```

复习时不要从“背题”开始，而要从一个具体请求开始：它从哪里进入、经过哪些校验、读取或修改了什么数据、失败时如何恢复、如何被测试证明。能把这条链路讲完整，八股才真正转化成项目能力。
