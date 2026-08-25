# AI Agent 功能代码讲解目录

面向对象：准备 AI 应用开发岗位面试，希望结合真实项目理解 Agent、Tool Calling、RAG、多轮任务和生产化设计的学习者。

本文不是通用 Agent 概念清单，而是依据当前仓库实际代码整理的阅读路线。建议每一章都按四个问题学习：

1. 这一层解决什么业务问题？
2. 请求从哪里进入，又流向哪里？
3. 为什么不能只让大模型直接回答？
4. 这部分在面试中如何用项目语言表达？

## 一、先建立系统全景

### 1. Agent 在摄影预约平台中解决什么问题

- 1.1 普通问答：回答摄影、平台使用等开放问题
- 1.2 真实资源搜索：查找摄影师、作品、套餐和企划
- 1.3 多模态理解：分析参考图并据此检索相似资源
- 1.4 业务任务：关注摄影师、发布企划、发布套餐和创建预约
- 1.5 页面协作：理解用户当前正在浏览的作品、摄影师、套餐或企划
- 1.6 拍摄辅助：查询地点、天气、日照窗口并生成拍摄建议

### 2. 普通聊天、RAG 和 Agent 在本项目中的边界

- 2.1 普通聊天只依赖对话历史和系统提示词
- 2.2 RAG 负责从平台真实资源中检索候选并约束回答
- 2.3 Agent 在 RAG 之上增加意图、决策、工具、任务状态与写操作
- 2.4 为什么“模型会回答”不等于“系统能可靠完成任务”
- 2.5 当前架构的核心思想：确定性流程优先，LLM 决策层渐进接管

### 3. 一条消息的端到端调用链

```text
移动端 AIAssistantPage
  -> mobile-app/src/api/ai.ts
  -> POST /api/v1/ai/conversations/{id}/messages
  -> backend/app/api/v1/ai.py
  -> ai_service.send_ai_message
  -> 意图分类 / 决策路由 / 视觉分析 / 检索或工具
  -> 业务流程或模型生成回答
  -> AIMessage + metadata + AgentTrace 持久化
  -> 移动端按 references、task_state、shoot_context 等结构化渲染
```

- 3.1 用户消息为什么要先持久化再执行 Agent
- 3.2 `send_ai_message` 为什么是当前系统的总编排入口
- 3.3 `metadata` 如何成为前后端之间的 Agent 协议
- 3.4 成功、空结果、澄清、待确认和失败分别怎样返回

关键代码：

- `mobile-app/src/pages/AIAssistantPage.vue`
- `mobile-app/src/api/ai.ts`
- `backend/app/api/v1/ai.py`
- `backend/app/schemas/ai.py`
- `backend/app/services/ai_service.py`

## 二、前端 Agent 交互层

### 4. 会话、消息与附件

- 4.1 创建会话、加载历史和发送消息的 API
- 4.2 文本、图片附件、页面上下文和任务表单如何组成一次请求
- 4.3 70 秒请求超时背后的同步 Agent 调用特点
- 4.4 消息中的普通文本与结构化元数据如何分工
- 4.5 引用卡片、拍摄环境卡片和业务操作入口如何渲染

### 5. Page Context：把“我正在看的这个”交给 Agent

- 5.1 为什么只发送聊天文本无法理解“这个摄影师”“这个套餐”
- 5.2 作品、摄影师、套餐、企划四类上下文的数据结构
- 5.3 上下文裁剪、列表限长和字段清洗
- 5.4 `sessionStorage` 一次性 handoff 与 10 分钟有效期
- 5.5 后端为什么仍要重新解析和校验页面资源
- 5.6 页面图片如何转成隐式视觉附件

关键代码：

- `mobile-app/src/utils/aiPageContext.ts`
- `mobile-app/src/components/AIPageContextCard.vue`
- `backend/app/services/ai_service.py` 中 `_normalize_page_context`、`_resolve_page_context`、`_build_page_context_prompt`

### 6. 前端任务表单与确定性提交

- 6.1 对话收集槽位与传统表单提交的关系
- 6.2 `task_submission` 为什么可以绕过一次不必要的意图猜测
- 6.3 发布与保存草稿如何作为明确用户动作传给后端
- 6.4 客户端导航动作与服务端写操作的边界

## 三、会话协议与状态模型

### 7. 会话和消息如何持久化

- 7.1 `AIConversation` 与 `AIMessage` 的表关系
- 7.2 为什么用户消息和助手消息都保存 `metadata`
- 7.3 对话历史如何重新拼装成模型输入
- 7.4 标题生成、消息排序和用户数据隔离
- 7.5 历史记录既是聊天上下文，也是任务状态存储

关键代码：

- `backend/app/models/ai_conversation.py`
- `backend/app/services/ai_service.py` 中会话 CRUD 与 `_build_provider_messages`

### 8. Agent 的统一数据契约

- 8.1 `AgentIntent`：意图、置信度、槽位和缺失槽位
- 8.2 `AgentSlots`：城市、预算、风格、日期、时间和业务字段
- 8.3 `AgentTaskState`：任务类型、状态、已收集槽位和待执行动作
- 8.4 `PendingToolAction`：写工具等待确认时保存什么
- 8.5 `normalize_agent_metadata` 为什么是兼容旧消息的重要边界
- 8.6 Pydantic 严格 Schema 如何减少模型输出的不确定性

关键代码：

- `backend/app/services/ai_agent_contracts.py`
- `backend/app/services/ai_agent_decision_contracts.py`

## 四、意图识别、路由与决策

### 9. 规则意图识别与槽位提取

- 9.1 `recognize_intent_by_rules` 支持哪些业务意图
- 9.2 如何识别资源搜索、关注、发布企划、发布套餐和预约
- 9.3 城市、预算、风格、日期、时间、时长等槽位如何提取
- 9.4 否定表达、隐式标题和表单式文本如何处理
- 9.5 规则方案的优点、脆弱点与适用边界

关键代码：

- `backend/app/services/ai_orchestrator_service.py`
- `backend/app/services/ai_domain_synonyms.py`

### 10. 混合意图分类器

- 10.1 rules、LLM 和 hybrid 三种分类模式
- 10.2 模型分类输入为什么包含规则候选和进行中的任务
- 10.3 JSON 输出清洗、Schema 校验与低置信度回退
- 10.4 规则与模型不一致时如何选择结果
- 10.5 分类耗时、模型名称和 fallback 原因如何进入诊断元数据

关键代码：

- `backend/app/services/ai_intent_classifier_service.py`
- `backend/app/services/ai_intent_prompt.py`
- `backend/app/services/ai_agent_contracts.py` 中 `apply_intent_policy`

### 11. 统一 LLM 决策层

- 11.1 决策层为什么输出 `chat`、`search`、`read_tool`、`clarify` 等有限动作
- 11.2 工具目录、用户角色、对话历史、页面上下文如何进入决策 Prompt
- 11.3 `AgentDecision` 如何限制工具名、参数和输出形状
- 11.4 `resolve_decision_plan` 如何做服务端二次裁决
- 11.5 为什么模型选中了工具，也不代表后端一定执行
- 11.6 决策结果与旧意图路由如何做 shadow 对比

关键代码：

- `backend/app/services/ai_agent_decision_prompt.py`
- `backend/app/services/ai_agent_decision_service.py`
- `backend/app/services/ai_agent_decision_contracts.py`

### 12. 灰度路由与渐进式重构

- 12.1 `legacy`、`shadow`、`tool_loop` 三种路由模式
- 12.2 按用户或会话稳定分桶的意义
- 12.3 shadow 模式为什么只记录差异、不改变线上行为
- 12.4 决策层接管后如何避免重复调用意图分类 LLM
- 12.5 接管失败时如何退回原有分类与编排路径
- 12.6 如何用覆盖率、分歧率和工具选择准确率决定扩大灰度

关键代码：

- `backend/app/services/agent_routing_gate.py`
- `backend/app/services/ai_service.py` 中 routing rollout 与 decision plan 分支
- `backend/scripts/agent_rollout_report.py`

## 五、Tool Calling 与安全执行

### 13. 工具注册中心与参数 Schema

- 13.1 `ToolSpec` 描述了工具的哪些生产属性
- 13.2 只读工具与写工具的划分
- 13.3 `llm_selectable`、`proposal_only`、`allowed_roles`、`requires_active_task`
- 13.4 工具别名为什么需要统一解析
- 13.5 模型可见的工具目录为什么只是注册表的安全子集
- 13.6 如何新增一个工具而不把执行逻辑散落到 Prompt 中

当前核心工具：

- `get_shoot_context`
- `search_photographers`
- `search_portfolio_items`
- `search_packages`
- `search_projects`
- `search_bookable_packages`
- `get_available_slots`
- `follow_photographer`
- `create_project`
- `publish_package`
- `create_booking`

关键代码：`backend/app/services/ai_tool_policy_service.py`

### 14. 工具授权与风险分级

- 14.1 `READ_ONLY`、`REVERSIBLE_WRITE`、`SENSITIVE_WRITE`、`FORBIDDEN`
- 14.2 `NONE`、`ONCE`、`TWICE`、`TRADITIONAL_UI`、`FORBIDDEN` 确认策略
- 14.3 用户角色、当前任务、写工具开关如何参与授权
- 14.4 为什么实体 ID 不能由模型自由编造
- 14.5 后端如何从真实检索结果和任务状态补全关键参数
- 14.6 参数验证失败、未注册工具和越权调用如何拒绝

### 15. 写操作确认、幂等和审计

- 15.1 写操作为什么先生成 `pending_action`，下一轮确认后再执行
- 15.2 确认、取消、修改槽位三类用户回复如何区分
- 15.3 幂等键如何防止重试或重复确认造成重复写入
- 15.4 `AgentActionLog` 记录输入、结果、状态、风险和耗时
- 15.5 可逆写操作为什么还要声明补偿动作
- 15.6 数据库事务失败后如何回滚并返回可解释错误

关键代码：

- `backend/app/services/ai_tool_policy_service.py` 中 `authorize_tool_call`、`prepare_tool_execution`、`build_idempotency_key`
- `backend/app/services/ai_agent_tool_service.py`
- `backend/app/models/ai_conversation.py` 中 `AgentActionLog`

### 16. 只读工具示例：真实拍摄环境查询

- 16.1 决策层何时选择 `get_shoot_context`
- 16.2 地点解析、歧义候选、天气和日照数据的组合
- 16.3 外部服务失败时如何返回结构化降级结果
- 16.4 为什么最终 LLM 只能复述工具给出的真实字段
- 16.5 前端如何把结构化结果渲染为专用卡片

关键代码：

- `backend/app/services/shoot_context_service.py`
- `backend/app/services/geocoding_service.py`
- `backend/app/services/weather_service.py`
- `mobile-app/src/components/AIShootContextCard.vue`

## 六、真实资源检索与 RAG

### 17. 资源索引如何建立

- 17.1 摄影师、作品和套餐如何统一成 `AIResourceDocument`
- 17.2 `search_text`、标签、城市、价格和原始 payload 的分工
- 17.3 `content_hash` 如何判断资源是否需要重新向量化
- 17.4 业务资源更新后如何刷新对应用户的索引
- 17.5 后台索引任务如何重试和记录状态

关键代码：

- `backend/app/models/ai_resource.py`
- `backend/app/models/ai_production.py` 中 `AIIndexJob`
- `backend/app/services/ai_resource_context_service.py`
- `backend/app/services/ai_resource_index_service.py`
- `backend/app/services/ai_index_job_service.py`

### 18. Embedding 与混合检索

- 18.1 Mock 与 OpenAI-compatible Embedding Provider
- 18.2 SQLite JSON 向量与 PostgreSQL pgvector 两类存储路径
- 18.3 结构化过滤为什么要先于或配合语义召回
- 18.4 关键词分、向量分、业务分、质量分和新鲜度分如何组合
- 18.5 城市、预算、风格、化妆和套餐内容如何做硬过滤
- 18.6 为什么最终候选还要经过相关性阈值判断
- 18.7 检索诊断如何记录候选数、结果数、耗时和算法版本

关键代码：

- `backend/app/services/ai_embedding_service.py`
- `backend/app/services/ai_retrieval_service.py`
- `backend/app/services/ai_observability_service.py`

### 19. Search Tool：把 RAG 封装成标准工具

- 19.1 决策层如何选择具体的 `search_*` 工具
- 19.2 工具参数如何转换成检索层的结构化条件
- 19.3 摄影师、作品、套餐为什么复用文档检索
- 19.4 企划为什么复用独立的业务推荐服务
- 19.5 工具返回如何统一成 `items + references + diagnostics`
- 19.6 为什么工具结果还要生成“只能引用真实候选”的提示词

关键代码：`backend/app/services/ai_search_tool_service.py`

### 20. 引用约束与防幻觉

- 20.1 `references` 如何把真实资源交给前端和模型
- 20.2 `citation_policy.allowed_resource_ids` 如何限制可引用范围
- 20.3 空检索为什么不能让模型自由补充推荐
- 20.4 `build_retrieval_context` 如何把候选转换成受约束上下文
- 20.5 结构化卡片为什么比只返回自然语言更可靠

### 21. 多模态 RAG

- 21.1 图片上传后如何进入视觉分析流程
- 21.2 视觉结果如何规范成风格、场景、色彩等结构化特征
- 21.3 图片分析如何补充意图槽位和检索文本
- 21.4 图片向量与文本向量如何共同参与候选排序
- 21.5 无新图片时如何复用上一轮视觉分析

关键代码：

- `backend/app/services/ai_vision_service.py`
- `backend/app/services/ai_multimodal_embedding_service.py`
- `backend/app/services/ai_multimodal_evaluation_service.py`

## 七、多轮任务与业务工作流

### 22. 多轮上下文不是简单拼接历史

- 22.1 如何从历史消息元数据中恢复最新任务状态
- 22.2 新槽位与旧槽位如何合并，哪些字段需要覆盖而不是追加
- 22.3 “换一个”“第二个”“就这个”如何引用历史候选
- 22.4 为什么资源 ID 必须从已展示候选中解析
- 22.5 任务取消后如何清除待执行动作

### 23. 搜索细化与历史资源引用

- 23.1 `search_context` 保存了哪些检索条件和已推荐 ID
- 23.2 “换一个”如何继承旧条件并排除旧结果
- 23.3 新条件如何覆盖继承条件
- 23.4 重复推荐率如何计算并进入质量指标
- 23.5 为什么搜索任务状态与发布、预约任务必须隔离

关键代码：`backend/app/services/ai_search_context_service.py`

### 24. 发布企划工作流

- 24.1 如何从自然语言和表单提交构造企划槽位
- 24.2 缺少字段时如何逐步追问
- 24.3 如何生成可确认的企划摘要
- 24.4 保存草稿与正式发布的区别
- 24.5 确认后如何调用 `create_project`

### 25. 发布套餐工作流

- 25.1 摄影师角色限制在哪里生效
- 25.2 套餐名称、价格、时长、张数、服务内容如何收集
- 25.3 参考图缺失或跳过参考图如何处理
- 25.4 修改已收集字段后为什么要重新确认
- 25.5 确认后如何调用 `publish_package`

### 26. 预约工作流与 Planner

- 26.1 套餐、摄影师、日期、时间和时长的槽位依赖
- 26.2 如何从上一轮引用资源解析真实套餐和摄影师
- 26.3 如何查询档期并推荐附近日期
- 26.4 Planner 如何把推荐、查档期和创建预约拆成步骤
- 26.5 预约状态机如何从收集信息走到待确认和已执行
- 26.6 创建订单失败后如何保留可继续修改的任务状态

关键代码：

- `backend/app/services/ai_booking_service.py`
- `backend/app/services/ai_planner_service.py`
- `backend/app/services/ai_agent_tool_service.py`

## 八、模型接入、错误恢复与降级

### 27. Provider 抽象

- 27.1 `AIProvider` 协议如何隔离业务层和模型供应商
- 27.2 Mock Provider 为什么能支持本地开发和稳定测试
- 27.3 OpenAI-compatible Provider 如何处理文本与图片消息
- 27.4 文本模型和视觉模型如何分别路由
- 27.5 模型返回中的 provider、model、token 等元数据如何保留

关键代码：`backend/app/services/ai_provider.py`

### 28. 失败恢复与可用性设计

- 28.1 Primary Provider 失败后如何切换 fallback
- 28.2 图片模型失败时如何退回文本能力
- 28.3 分类器超时或非法 JSON 时如何回到规则结果
- 28.4 决策层不接管时如何回到 legacy 路由
- 28.5 检索空结果与检索异常为什么需要不同回复
- 28.6 日志记录失败为什么不能拖垮主聊天流程

### 29. 配置与版本化

- 29.1 Provider、Embedding、分类模式和灰度开关的环境配置
- 29.2 Prompt、Orchestrator、Index 和 Tool Schema 为什么分别版本化
- 29.3 版本号如何写入消息元数据和 Trace
- 29.4 为什么离线评测必须知道当时使用的版本

关键代码：

- `backend/app/core/config.py`
- `.env.example`

## 九、可观测性、评测与测试

### 30. Trace、Action Log 和 Retrieval Log

- 30.1 `AgentTrace` 记录一轮 Agent 的总体结果
- 30.2 `AgentActionLog` 记录每次真实工具执行
- 30.3 `AgentRetrievalLog` 记录检索输入、候选和排序诊断
- 30.4 三种日志如何分别回答“路由错、工具错还是检索错”
- 30.5 延迟、token、fallback、引用资源和质量标记如何关联

关键代码：

- `backend/app/models/ai_conversation.py`
- `backend/app/models/ai_production.py`
- `backend/app/services/ai_trace_service.py`
- `backend/app/services/ai_observability_service.py`

### 31. 线上质量面板与灰度指标

- 31.1 成功率、fallback 率、平均延迟和空检索率
- 31.2 决策接管率、回退率和 shadow 分歧率
- 31.3 意图分类 agreement 与低置信度比例
- 31.4 重复推荐率和资源引用完整性
- 31.5 管理端质量接口如何聚合最近若干天数据

关键代码：

- `backend/app/api/v1/admin.py` 中 `/ai/quality-dashboard`
- `backend/app/services/ai_trace_service.py`
- `backend/scripts/agent_rollout_report.py`

### 32. 离线评测

- 32.1 Golden JSONL 用例的输入、期望意图和期望工具
- 32.2 如何评估规则路由和 LLM 工具选择
- 32.3 如何回放历史 Trace 比较新旧策略
- 32.4 Hybrid RAG 与 Multimodal RAG 分别评估什么
- 32.5 为什么 Agent 评测要拆成分类、工具、检索和最终结果多个层次

关键代码：

- `backend/evals/agent_phase1_golden.jsonl`
- `backend/evals/agent_phase_c_tool_selection.jsonl`
- `backend/evals/hybrid_rag_golden.jsonl`
- `backend/evals/multimodal_rag_golden.jsonl`
- `backend/scripts/evaluate_ai_agent.py`
- `backend/scripts/evaluate_hybrid_rag.py`
- `backend/scripts/evaluate_multimodal_rag.py`
- `backend/app/services/ai_offline_eval_service.py`

### 33. 自动化测试阅读路线

- 33.1 API 契约：会话、消息、附件和鉴权
- 33.2 意图与路由：规则、混合分类、决策接管和灰度
- 33.3 工具安全：Schema、角色、确认、幂等和重复调用
- 33.4 RAG：结构化过滤、混合排序、空结果和引用
- 33.5 多模态：图片分析、视觉检索和上下文复用
- 33.6 多轮工作流：企划、套餐、预约和取消
- 33.7 生产化：Trace、质量指标、索引任务和回退

建议重点阅读：

- `backend/tests/test_ai_api.py`
- `backend/tests/test_ai_intent_classifier.py`
- `backend/tests/test_ai_phase_a_routing.py`
- `backend/tests/test_ai_phase_b_tool_routing.py`
- `backend/tests/test_ai_phase_c_rollout.py`
- `backend/tests/test_ai_hybrid_rag.py`
- `backend/tests/test_ai_multimodal_rag.py`
- `backend/tests/test_ai_booking_service.py`
- `backend/tests/test_ai_productionization.py`
- `backend/tests/test_ai_map_weather_tool.py`

## 十、架构复盘与面试表达

### 34. 当前架构的优点

- 34.1 真实数据访问集中在服务和工具层，模型不直接碰数据库
- 34.2 写操作具备确认、权限、事务、幂等和审计
- 34.3 RAG 输出带结构化引用，可在前端展示并约束生成
- 34.4 规则、LLM 和业务工作流能按风险选择不同确定性程度
- 34.5 shadow 与灰度机制降低 Agent 路由重构风险
- 34.6 Trace、离线集和自动化测试形成基本评测闭环

### 35. 当前架构值得继续改进的地方

- 35.1 `ai_service.py` 体积过大，承担了过多编排和领域逻辑
- 35.2 任务状态主要藏在消息 metadata 中，查询和迁移成本较高
- 35.3 同步请求串行执行多次模型与检索调用，端到端延迟较高
- 35.4 工具循环目前更接近“单步决策 + 确定性执行”，还不是通用多步自主循环
- 35.5 Prompt、工具结果和元数据协议仍需更严格的契约测试
- 35.6 成本统计、模型限流、熔断和分布式 Trace 仍可加强

### 36. 面试讲解模板

- 36.1 业务背景：摄影预约平台需要从问答升级到真实资源与业务操作
- 36.2 技术难点：意图不稳定、资源必须真实、写操作有风险、多轮状态易丢失
- 36.3 核心方案：混合意图识别 + 灰度决策层 + 工具注册中心 + 混合 RAG + 确认式工作流
- 36.4 可靠性方案：Schema 校验、权限、幂等、审计、fallback、引用约束
- 36.5 评测方案：单元测试、Golden Set、Trace 回放和线上质量指标
- 36.6 结果表达：说明系统获得了什么能力，以及如何证明它比“直接调用模型”更可靠

建议用下面这句话概括项目：

> 我在摄影预约业务中实现的不是一个只会聊天的机器人，而是一套受控 Agent：它能理解多轮意图和页面上下文，从真实业务数据中做混合检索，通过严格 Schema 选择工具，并在权限、确认、幂等和审计约束下完成发布与预约等操作；同时使用 shadow 灰度、Trace 和离线评测持续验证路由与工具选择质量。

## 十一、推荐学习顺序

### 第一轮：先跑通主链路

1. 第 1～3 章：建立全景
2. 第 7～8 章：理解消息和 metadata
3. 第 9～12 章：理解意图、决策和灰度路由
4. 第 13～15 章：理解工具安全边界
5. 第 17～20 章：理解真实资源检索

### 第二轮：按业务流程深挖

1. 第 22～23 章：多轮上下文
2. 第 24～26 章：企划、套餐和预约工作流
3. 第 5、16、21 章：页面上下文、地图天气和多模态

### 第三轮：补齐生产化能力

1. 第 27～29 章：Provider、降级和版本
2. 第 30～33 章：日志、指标、评测和测试
3. 第 34～36 章：架构复盘与面试表达

## 十二、建议的代码阅读方式

每读一个能力，按以下顺序追踪，不要只在 `ai_service.py` 内部跳转：

1. 从前端请求或用户场景开始。
2. 查看 API Schema，确认输入输出协议。
3. 进入 `send_ai_message` 找到该场景的路由分支。
4. 继续进入专用 service，确认真实业务数据来自哪里。
5. 查看写入的 `metadata`、Action Log 或 Trace。
6. 最后阅读对应测试，确认设计者认定的边界行为。

完成全部目录后，应当能够独立回答：

- 为什么该项目既需要规则路由，也需要 LLM 决策？
- 为什么 RAG 仍然要封装成工具？
- 模型为什么不能直接执行写操作？
- 多轮任务状态和普通聊天历史有什么区别？
- 如何证明一次工具调用和一次资源推荐是可靠的？
- 如果新增“申请企划”工具，需要改哪些契约、权限、状态、日志和测试？
