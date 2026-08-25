# Agent 记忆与任务系统交接文档

更新时间：2026-08-23

## 目标

解决 Agent 在用户追问“第二个方案有什么注意事项”时丢失方案详情、错误降级到普通聊天的问题，并继续完成工作记忆、任务会话、长期记忆和历史压缩体系。

## 已完成

### 1. Redis 工作记忆

- 文件：`backend/app/services/agent_working_memory_service.py`
- 保存当前任务类型、任务状态、结构化槽位、表单、资源快照、选中资源、最近工具状态和事件。
- 默认 TTL 24 小时。
- 资源和事件数量有上限，避免 Redis 无限增长。
- 支持“第一个/第二个方案”“这个/那个/刚才”等确定性引用解析。
- 任务退出会暂停任务，不会立即删除状态，便于恢复和审计。

### 2. 任务会话持久化

- 文件：`backend/app/models/agent_task_session.py`
- 文件：`backend/app/services/agent_task_session_service.py`
- 表：`agent_task_sessions`、`agent_task_resources`、`agent_task_events`
- Redis 丢失时，可以从数据库恢复最近的 active/paused 任务。
- 迁移：`backend/migrations/versions/n4e5f6a7b8c9_add_agent_task_sessions.py`

### 3. AI 服务接入

- 文件：`backend/app/services/ai_service.py`
- 搜索结果会写入 Redis 和数据库资源快照。
- 决策层可读取当前任务上下文。
- 资源详情查询会注入权威资源快照，避免模型自行编造或遗漏方案注意事项。
- 明确退出任务时会调用 `finalize_task_memory(..., outcome="paused")`。
- 搜索路径已修复为接收 `update_working_memory` 的返回值，避免把旧内存同步回数据库。

### 4. 长期记忆

- 模型：`backend/app/models/agent_memory.py`
- 服务：`backend/app/services/agent_long_term_memory_service.py`
- 表：`agent_memory_episodes`、`agent_user_memories`
- 任务总结目前以确定性规则生成，提取城市、风格等偏好候选。
- 初始置信度为 `0.55`，不同任务提供重复证据时增加 `0.10`。
- 置信度达到 `0.75` 才变成 `active`。
- 同一 `task_id` 幂等，不会重复累计证据。
- 已提供只读取 active 记忆的接口；candidate 不应注入模型上下文。
- 迁移：`backend/migrations/versions/o5f6a7b8c9d0_add_agent_long_term_memory.py`

### 5. 测试与验证

- `C:\Python314\python.exe -m py_compile ...` 已通过。
- `C:\Python314\python.exe -m pytest backend\tests\test_agent_long_term_memory.py -q`：2 passed。
- `C:\Python314\python.exe -m alembic -c alembic.ini upgrade head` 已成功执行到 `o5f6a7b8c9d0`。

## 尚未完成

### A. 长期记忆注入模型上下文

当前原则：只注入 `status="active"` 的长期记忆，并作为低优先级偏好提示。

优先接入最终回复模型的 `extra_system_prompts`，提示必须明确：

1. 当前用户消息优先；
2. 当前任务表单和工具返回的资源快照优先；
3. 长期记忆只是弱偏好参考；
4. 不得把长期记忆当作本轮已确认事实；
5. 不得用长期记忆替代或缩小检索条件，除非用户本轮明确确认。

不要把 candidate 记忆注入分类器、决策器或最终模型。

### B. 任务切换与意图转换

推荐优先级：

1. 明确取消/退出/切换表达；
2. 当前任务中的资源引用解析；
3. 当前任务表单是否仍能接收新槽位；
4. 明确的新任务意图；
5. 向量相似度只能作为辅助信号，不能单独清除任务数据。

任务切换时应先将旧任务标记为 `paused` 或 `abandoned`，保留数据库审计记录，再创建新任务。不要直接物理删除旧任务。

### C. 超过 100 轮的历史压缩

建议按任务结束触发，而不是机械地每 100 条原始消息截断：

- 触发条件：对话消息数超过 100，且当前任务状态为 paused/completed/cancelled/abandoned；
- 异步生成 episode 摘要；
- 保存用户画像、已确认偏好、任务目标、工具结果摘要、未完成事项和关键资源引用；
- 原始消息保留数据库，不要直接删除；
- 后续上下文只加载最近窗口 + 相关任务摘要 + active 长期记忆。

### D. 补充测试

建议新增：

- “第二个方案”的详情追问仍命中原始资源快照；
- Redis 清空后从数据库恢复任务并解析资源引用；
- 明确退出后任务变为 paused，且生成一条 episode；
- candidate 长期记忆不进入 prompt；
- active 长期记忆只作为低优先级提示；
- 明确新意图切换任务时，旧任务保留且新任务独立创建。

## 关键约束

- Redis 是工作记忆，不是最终事实来源。
- 数据库是任务状态、资源快照、事件和长期记忆的持久化来源。
- 工具返回的结构化资源详情优先级高于模型历史记忆和长期偏好。
- 不要用单次搜索结果直接形成用户长期偏好。
- 不要因为一次低相似度输入就清除任务表单。
- 当前工作树存在大量与本任务无关的用户改动，继续修改时不要回滚或重排这些文件。

## 推荐下一窗口执行顺序

1. 检查 `ai_service.py` 是否已有 `long_term_memory_prompt` 接入；若没有，完成 A。
2. 运行 `py_compile` 和长期记忆定向测试。
3. 补任务切换、Redis 恢复、资源追问测试。
4. 设计并实现超过 100 轮的异步历史压缩任务。
5. 最后运行完整后端测试集，记录已有警告与失败，不要把无关历史失败误判为本次改动回归。
