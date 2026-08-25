# Agent 历史任务记忆与当前任务上下文隔离修复计划

更新时间：2026-08-24  
目标读者：负责修复 Agent 记忆、任务、上下文构建与 trace 的 Codex/开发者

## 1. 背景与设计目标

保留历史任务的结构化数据是正确方向。Agent 应该能够知道用户过去做过哪些任务、任务条件、查看过哪些资源、选择了什么以及最终结果如何。

本次问题不在于“保存了历史任务”，而在于系统把以下两类数据放进了同一份可变状态，并在每轮推理中默认加载：

1. 当前任务执行所需的活动状态；
2. 只用于审计、恢复和按需回忆的历史任务数据。

历史任务可以永久保留，但历史任务的原始 `slots`、`form`、`resources` 和 `selected_resource` 不应自动成为当前任务的输入参数。历史数据只有在用户明确回顾、恢复旧任务，或系统判断其与当前问题强相关时，才应以受限摘要的形式进入上下文。

本计划需要同时满足：

- 历史任务结构化数据不丢失；
- Redis 丢失后仍能恢复当前任务；
- 新任务不继承旧任务槽位；
- Agent 可以回答“我之前做过什么任务”；
- Agent 可以显式恢复旧任务；
- 当前任务可以引用本任务内的资源；
- 普通聊天和新任务不会被历史任务强行路由；
- trace 能说明每段上下文来自哪里、为何被加载。

## 2. 已确认的问题

测试账户：`agenttest2`，`user_id=18`，`conversation_id=12`。

数据库与 trace 表明：

- 旧的 `portfolio_item_search` 被暂停后，结构化数据得到了保留；
- 随后的 `package_search` 除了新条件“大理、写真”外，还包含旧任务中的日系、胶片、自然光、复古、妆造等 slots；
- 普通的烟台拍照地点咨询连续被决策层路由到 `get_shoot_context`；
- 大理新闻查询曾被旧旅拍任务上下文影响，错误返回摄影师推荐；
- `agent_user_memories` 中相关记录仍为 `candidate`，没有进入 active 长期记忆，因此长期用户偏好表不是本次污染的首要来源。

直接根因位于 `backend/app/services/agent_working_memory_service.py`：

```python
if slots:
    memory["slots"] = {**(memory.get("slots") or {}), **slots}
```

当前 Redis key 仅以用户和 conversation 为边界：

```text
agent:working-memory:{user_id}:{conversation_id}
```

当 `task_type` 改变时，系统仍先读取同一份 Redis 对象并合并 slots。数据库虽然随后创建了新的 `AgentTaskSession`，但新任务保存进去的已经是污染后的状态。

## 3. 推荐的分层存储模型

不要删除历史任务，而应把“活动工作区”“历史任务账本”“可检索任务记忆”“用户长期偏好”分成四层。

### 3.1 L0：当前请求上下文

生命周期只限于一轮请求，不持久化为跨任务状态。

包含：

- 当前用户消息；
- 当前页面上下文；
- 当前请求附件；
- 本轮工具结果；
- 本轮明确提取出的 slots；
- 本轮决策历史的有限窗口。

本层优先级最高，任何历史数据都不能覆盖本层事实。

### 3.2 L1：活动任务工作区

Redis 只保存一个具体 `task_id` 的可变工作副本，不保存 conversation 中所有任务的混合状态。

推荐 key：

```text
agent:active-task:{user_id}:{conversation_id} -> {task_id, revision, task_type}
agent:task-workspace:{task_id} -> working memory payload
```

第一条 key 是活动任务指针，第二条 key 是按任务隔离的工作区。

工作区 payload 必须包含：

```json
{
  "schema_version": "agent_task_workspace_v2",
  "task_id": "uuid",
  "user_id": 18,
  "conversation_id": 12,
  "task_type": "package_search",
  "status": "active",
  "revision": 4,
  "slots": {},
  "form": {},
  "resources": [],
  "selected_resource": null,
  "last_tool": null,
  "events": [],
  "updated_at": "..."
}
```

约束：

- `task_id`、`user_id`、`conversation_id`、`task_type` 必须在读取后校验；
- 新任务必须创建新 workspace，禁止从旧 task workspace 深拷贝；
- 同一 task 内的多轮补充才允许 merge slots；
- task type 变化时禁止 merge，即使 conversation 相同；
- paused/completed/cancelled 后删除活动指针；task workspace 可以短期保留用于快速恢复，也可以直接依赖数据库恢复；
- Redis 永远不是历史任务的唯一事实来源。

### 3.3 L2：数据库历史任务账本

现有表基本适合承担这一层：

- `agent_task_sessions`：任务身份、状态、最终 slots/form、摘要；
- `agent_task_resources`：任务涉及的真实资源及快照；
- `agent_task_events`：任务事件时间线；
- `agent_memory_episodes`：任务结束后的紧凑摘要和结果。

这些数据应该长期保存，但默认不直接注入当前决策器。

建议把历史任务视为 append-oriented ledger：

- 任务切换时旧任务变为 paused，而不是被新任务覆盖；
- 资源、结果、关键操作保留 task_id 归属；
- event 记录槽位变化、搜索、选择、恢复、暂停和完成；
- 如需审计完整变化，后续可增加 slot patch event，而不是依赖最终 slots 还原全过程。

建议为 `AgentTaskSession` 增加或明确以下字段：

- `parent_task_id`：一个任务由旧任务派生时建立弱关联，不用于继承 slots；
- `resume_count`：恢复次数；
- `context_version`：生成 episode 时使用的结构版本；
- `result_summary` 或统一放入 `structured_summary.result`；
- `archived_at`：与 paused/completed 区分是否仍值得展示。

上述字段不是首轮修复的硬依赖。首轮应优先完成上下文隔离。

### 3.4 L3：按需检索的任务记忆

`agent_memory_episodes` 应承担“Agent 知道过去做过什么”的主要入口，但不能每轮把所有 episode 都塞进 prompt。

每个 episode 推荐保存：

```json
{
  "task_type": "package_search",
  "goal": "寻找大理旅拍方案",
  "confirmed_constraints": {
    "city": "大理",
    "styles": ["写真"]
  },
  "resources": [
    {
      "resource_type": "packages",
      "resource_id": "...",
      "name": "大理旅拍全程跟拍",
      "role": "selected"
    }
  ],
  "result": {
    "status": "paused",
    "selected_resource_id": "..."
  },
  "open_items": [],
  "started_at": "...",
  "ended_at": "..."
}
```

任务记忆的读取应分为三种模式：

1. `none`：默认模式，不读取历史任务；
2. `summary`：用户问“之前做过什么”“之前找的大理方案”等，只加载最多 3～5 条相关 episode 摘要；
3. `resume`：用户明确要求“继续上次的大理方案”，选择一个 task_id，从数据库重建该任务的独立 workspace。

禁止把历史 episode 的 slots 自动合并到新任务。恢复旧任务必须是显式状态转换，不是隐式字段继承。

### 3.5 L4：用户长期偏好

`agent_user_memories` 只保存跨多个任务反复出现、达到置信阈值的稳定偏好，例如长期偏爱日系风格。

它与历史任务的区别是：

- 历史任务回答“用户做过什么”；
- 长期偏好回答“用户通常偏好什么”；
- 当前任务回答“用户现在要做什么”。

长期偏好只能作为低优先级建议，不得变成本轮搜索过滤条件，除非用户明确确认。

## 4. 上下文装配规则

新增统一的 `AgentContextEnvelope` 概念。即使不立刻增加正式模型，也要按这个结构组织代码：

```json
{
  "current_request": {},
  "active_task": {},
  "referenced_task_episodes": [],
  "active_user_memories": [],
  "recent_dialogue": [],
  "provenance": []
}
```

优先级固定为：

```text
本轮用户明确输入
  > 本轮页面上下文和可信工具结果
  > 当前 task_id 的表单/slots/资源
  > 用户明确引用的历史任务摘要
  > active 长期偏好
  > 普通最近对话
```

关键规则：

- 分类器和决策器默认只能读取当前消息、有限最近历史和当前 task 摘要；
- 历史 task episode 只有命中明确回忆/恢复意图后才能进入；
- 长期偏好不进入确定性工具参数；
- 历史资源快照只有在用户明确引用该历史任务或恢复任务时才能读取；
- 当前没有 active task 时，不得把最近 paused task 伪装成 active task；
- paused task 只能作为 `resume_candidate`，不能作为 `active_task_context`；
- “这个、第二个、刚才那个”等引用仅在当前 active task 内解析；如果没有 active task，应要求用户确认指的是哪个历史任务，不能猜测最近 paused task。

## 5. 任务切换状态机

### 5.1 同一任务内更新

满足以下条件才允许 merge slots：

- workspace 的 `task_id` 与数据库 active task 相同；
- `task_type` 相同；
- 用户消息被识别为任务补充、资源追问、筛选修改或任务内动作；
- revision 未发生并发冲突。

### 5.2 创建新任务

检测到明确的新任务后：

1. 将旧 active task 标记为 paused；
2. 为旧任务生成/更新 episode，但不删除历史结构数据；
3. 删除 `agent:active-task:{user_id}:{conversation_id}` 指针；
4. 创建新的 `AgentTaskSession` 和新的 task_id；
5. 用 `empty_working_memory(task_id=..., task_type=...)` 创建全新 workspace；
6. 只写入本轮明确提取的 slots；
7. 设置新的 active pointer；
8. trace 记录 `task_transition=replace`、旧 task_id、新 task_id。

### 5.3 暂时闲聊

普通闲聊不需要销毁历史任务，但也不应把任务 slots 注入无关决策。

推荐策略：

- active task 可以保持 active，但上下文门控判断本轮是否 `task_related`；
- 如果连续出现明确换话题，可将任务 paused 并清除 active pointer；
- 无论哪种策略，普通聊天不得修改 task slots、资源和 selected resource。

### 5.4 恢复旧任务

用户明确表达“继续刚才/上次的大理方案”时：

1. 查询与文本相关的 paused task episodes；
2. 唯一高置信命中时恢复该 task；
3. 多个候选时展示简短候选让用户选择；
4. 从数据库 task session/resources 重建该 task_id 的 workspace；
5. 将其他 active task 暂停；
6. 设置 active pointer；
7. 不创建新 task，不把该任务数据复制进另一个 task。

## 6. 具体代码修复计划

### 阶段 A：修复 Redis 工作区隔离，阻断继续污染

涉及文件：

- `backend/app/services/agent_working_memory_service.py`
- `backend/app/services/agent_task_session_service.py`
- `backend/app/services/ai_service.py`

实施项：

1. 为 working memory payload 增加必填 `task_id`。
2. 新增 active pointer 的 get/set/clear 方法。
3. 将 workspace key 改为按 task_id 隔离。
4. 保留旧 key 的短期兼容读取，但读取后必须校验 task type，并迁移到新 key；不一致时直接丢弃旧缓存。
5. 修改 `update_working_memory()`：
   - 传入 task_id；
   - 只有 task_id 和 task_type 均相同时才 merge；
   - 不一致时抛出明确异常或创建 empty workspace，禁止静默 merge。
6. 搜索任务开始前先确定 durable task_id，再更新 Redis，而不是先产生无 task_id memory、同步时才决定任务身份。
7. pause/complete/cancel 时清除 active pointer。
8. Redis 恢复必须由 active pointer 指向一个数据库中仍为 active 的 task；不得用“最近 paused/active task”模糊恢复当前任务。

注意：现有 `load_latest_working_memory()` 查询 `ACTIVE = {"active", "paused"}`，这会把 paused task 恢复成当前任务。应拆成：

- `load_active_task_workspace()`：只允许 `status == "active"`；
- `load_resumable_task()`：按用户明确恢复请求查询 paused task。

### 阶段 B：修复新任务创建和槽位合并

实施项：

1. 把“判断新任务”和“写 working memory”拆开。
2. 新任务创建必须调用一个统一事务函数，例如：

```python
transition_to_new_task(
    db,
    user_id=user_id,
    conversation_id=conversation_id,
    task_type=task_type,
    initial_slots=current_turn_slots,
    message_id=user_message.id,
)
```

3. 该函数负责暂停旧任务、生成 episode、创建新 task、创建空 workspace、设置指针。
4. 不允许 `sync_working_memory()` 根据一份已经 merge 的 memory 猜测应该新建还是复用 task。
5. 对 task revision 使用乐观并发校验；必要时使用现有 Redis distributed lock：

```text
agent-task-transition:{user_id}:{conversation_id}
```

6. 并发请求只能有一个完成 task transition，另一个应重新读取 active pointer/revision。

### 阶段 C：将历史任务改为按需回忆

新增或扩展服务：

- 建议新增 `backend/app/services/agent_task_memory_retrieval_service.py`
- 扩展 `agent_long_term_memory_service.py`
- 调整 `ai_service.py` 的上下文装配

建议接口：

```python
list_recent_task_episodes(db, user_id, limit=10)
search_task_episodes(db, user_id, query, task_types=None, limit=5)
get_task_episode(db, user_id, task_id)
resume_task(db, user_id, conversation_id, task_id)
```

首版不必引入向量数据库，可以使用确定性字段匹配：

- task type；
- 城市；
- 资源名称；
- 时间范围；
- outcome；
- summary 关键词。

只有明确的历史回忆/恢复意图才调用这些接口。后续数据量增大后再增加 episode embedding。

### 阶段 D：限制历史和 previous search context

涉及文件：

- `backend/app/services/ai_service.py`
- 搜索上下文/refinement 相关服务
- `backend/app/services/agent_history_compression_service.py`

实施项：

1. `latest_search_context()` 返回值增加 task_id/task_type/revision。
2. refinement 只在当前 active task_id 与 search context task_id 相同时生效。
3. 新任务、普通无关聊天、历史回忆请求不得继承 previous search context。
4. `_decision_history()` 应优先读取当前 episode 开始后的消息；没有 active task 时使用更短的普通聊天窗口。
5. 历史压缩不能只生成 episode 后仍把全部旧消息持续交给 provider；provider context 应真正使用：

```text
最近消息窗口 + 当前任务消息/摘要 + 明确检索到的历史 episode
```

6. 数据库原始消息继续保留用于审计，不等于每轮都应发送给模型。

### 阶段 E：增加 provenance 和污染检测 trace

涉及文件：

- `backend/app/services/ai_trace_service.py`
- `backend/app/models/ai_production.py`，如需新增独立 JSON 字段
- `backend/app/services/ai_service.py`

至少在 `quality_flags` 或新的 context trace 中记录：

```json
{
  "active_task_id": "...",
  "active_task_type": "package_search",
  "workspace_source": "redis|database|new|none",
  "workspace_revision": 4,
  "previous_search_task_id": "...",
  "referenced_episode_ids": [],
  "long_term_memory_ids": [],
  "task_transition": "none|create|pause|resume|replace|complete",
  "stale_workspace_discarded": false,
  "task_type_mismatch": false,
  "cross_task_slots_blocked": [],
  "context_sources": ["current_message", "active_task", "recent_dialogue"]
}
```

增加防御性检查：

- active pointer 的 task_id 与 workspace task_id 不一致：丢弃缓存并 trace；
- workspace task_type 与数据库 task_type 不一致：丢弃缓存并 trace；
- previous search task_id 与 active task_id 不一致：禁止 refinement 并 trace；
- 历史 episode slots 进入当前 tool arguments：测试环境直接断言失败，生产环境删除字段并报警。

### 阶段 F：迁移现有污染数据

不要删除历史任务。迁移目标是修复 active 状态与污染后的任务快照。

步骤：

1. 部署前清理旧格式 Redis working-memory keys，或通过 schema version 自动失效。
2. 数据库中同时存在多个 active task 时，只保留最近且可验证的一个 active，其余转 paused。
3. 不应自动删除疑似污染 slots，因为无法稳定判断哪些条件是用户真实复用的。
4. 对明显异常任务可以生成审计报告，供人工或测试账户清理。
5. `agenttest2` 可作为专项验证账户；修复验证前建议暂停现有 active task，重新创建干净任务，但不要删除其 trace 和 episode。

## 7. 数据模型与迁移建议

首轮可以不新增数据库表，利用现有四张任务/记忆表完成修复。

若需要完善历史任务检索，建议优先扩展 `agent_memory_episodes.structured_summary`，避免立即增加重复表。

可选的后续表：

```text
agent_task_links
- source_task_id
- target_task_id
- relation_type: resumed_from | derived_from | related_to
- created_at
```

该表只描述任务关系，不传递 slots。不要用 `parent_task_id` 实现隐式继承。

迁移要求：

- 新 workspace schema 使用 `agent_task_workspace_v2`；
- 旧 `agent_working_memory_v1` 只做一次兼容读取；
- 没有 task_id 的旧缓存不得继续作为 active workspace；
- 数据库迁移和 Redis schema 切换应可独立回滚；
- 不回滚或删除现有任务、episode、resource、event 数据。

## 8. 必须新增的回归测试

### 8.1 工作区隔离

- 创建 `portfolio_item_search`，写入日系、胶片、妆造。
- 切换到 `package_search`，本轮只输入大理。
- 断言新任务 slots 只有本轮明确条件，不包含旧风格和妆造。
- 断言旧任务仍可在数据库查询，状态为 paused，并有 episode。

### 8.2 同任务正常继承

- 创建 package search，第一轮输入大理。
- 第二轮输入预算 2000。
- 断言同一 task_id 合并为大理 + 预算 2000。

### 8.3 Redis 缓存校验

- 构造 task_id/type 不匹配的 Redis payload。
- 断言系统丢弃缓存，从数据库恢复或创建干净 workspace。
- 断言 trace 标记 `stale_workspace_discarded=true`。

### 8.4 paused task 不自动恢复

- 只有一个 paused task，没有 active pointer。
- 发送普通聊天。
- 断言 paused task 不进入 active task context，也不影响 tool arguments。

### 8.5 显式恢复

- 保存两个 paused task：大理方案和重庆婚礼。
- 用户说“继续之前的大理方案”。
- 断言只恢复大理 task_id，不创建复制任务，不读取重庆 slots。

### 8.6 当前资源引用

- 当前 active package task 有三个资源。
- 用户问“第二个有什么注意事项”。
- 断言命中当前 task 的第二个资源快照。

### 8.7 历史任务引用歧义

- 没有 active task，但有多个历史任务。
- 用户问“第二个怎么样”。
- 断言系统要求说明任务，不从最近 paused task 猜测。

### 8.8 previous search context 隔离

- 旧 task 搜索摄影师。
- 新 task 查询新闻或地点。
- 断言旧搜索 refinement、exclude IDs、styles 不进入新请求。

### 8.9 长期偏好弱化

- active 长期偏好为日系。
- 当前请求明确要求纪实风。
- 断言工具参数只使用纪实风，长期偏好最多影响自然语言建议。

### 8.10 `agenttest2` trace 场景

复现以下序列：

1. 图片/作品搜索；
2. 婚礼方案；
3. 重庆天气；
4. 大理旅拍；
5. 大理新闻；
6. 山东烟台拍照地点。

验收：

- 新闻请求不返回摄影师推荐；
- 烟台拍照地点请求不因大理天气任务被强制调用 `get_shoot_context`；
- 每次任务切换的 task_id 清晰；
- trace 中没有跨 task slots；
- 历史任务仍能通过“我之前做过什么”查询到。

## 9. 推荐测试命令

先运行定向测试，再扩大范围：

```powershell
C:\Python314\python.exe -m pytest backend\tests\test_agent_long_term_memory.py -q
C:\Python314\python.exe -m pytest backend\tests\test_agent_task_service.py -q
C:\Python314\python.exe -m pytest backend\tests\test_ai_service.py -q
C:\Python314\python.exe -m pytest backend\tests\test_ai_phase_b_tool_routing.py -q
```

建议新建专项测试文件：

```text
backend/tests/test_agent_task_memory_isolation.py
```

若测试环境使用 fakeredis，每个测试必须重置 Redis client/key，防止测试之间再次出现缓存污染。

## 10. 验收标准

修复完成必须同时满足：

- 历史任务、资源、事件、episode 均保留；
- 新任务的 workspace 是空白创建，不继承旧 task slots；
- 同一任务的合法续轮仍能合并 slots；
- paused task 不会自动成为 active context；
- 用户可以列出和显式恢复历史任务；
- 历史任务摘要默认不进入分类器、决策器和工具参数；
- 长期偏好不会覆盖当前明确条件；
- previous search context 与 task_id 绑定；
- Redis 与数据库身份不一致时 fail closed；
- trace 能解释实际使用了哪些上下文来源；
- `agenttest2` 的跨任务场景不再复现污染。

## 11. Codex 推荐执行顺序

1. 先为现状补充失败测试，锁定 `agenttest2` 的跨任务污染。
2. 实现 task_id workspace 与 active pointer，不改历史任务表语义。
3. 修改任务切换顺序：先创建 durable task，再创建空 workspace。
4. 拆分 active task 恢复与 paused task 显式恢复。
5. 给 search context 加 task_id 校验。
6. 增加 task episode 的按需查询/恢复接口。
7. 收紧 decision history 和 provider history 的装配范围。
8. 增加 provenance trace 和失配报警。
9. 运行定向测试及 `agenttest2` 场景回放。
10. 最后再考虑 episode embedding、任务关系表和更复杂的自动回忆。

## 12. 实施约束

- 不删除历史任务数据来规避污染；
- 不通过全面禁用记忆来规避污染；
- 不把 paused task 当作默认 active task；
- 不让 LLM 自行决定 task_id、resource_id 或跨任务合并字段；
- 不用 conversation_id 作为任务状态的唯一隔离边界；
- 不把单次任务结果直接提升为长期偏好；
- 不回滚工作树中与本修复无关的现有修改；
- 每个阶段都先补回归测试，再修改实现。

最终目标不是让 Agent “忘记旧任务”，而是让它能够在正确的时候、以正确粒度回忆旧任务，同时保证当前任务拥有独立、可验证、不会被历史状态覆盖的工作区。
