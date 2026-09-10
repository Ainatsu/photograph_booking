# 阶段 C 实施计划：Workflow Runtime 与模板解析

前置确认：阶段 A（capability registry，7 个能力已注册，入口 `execute_capability`）与阶段 B（`agent_workflow_contracts.py` + `agent_workflow_store.py` + 三张表 + migration f9a0b1c2d3e4）均已就位。store 已提供 `get_ready_steps` / `mark_step_running(resolved_input=...)` / `persist_step_result` / `retry_step` / `recover_workflow_run` 等原语，接缝全部预留。

范围（按用户选择）：**纯 runtime + 模板解析 + 测试**，不改 `ai_service.py`，SSE 镜像留阶段 D。

## 1. 新增 `backend/app/services/agent_workflow_templates.py`（白名单模板解析）

- `TemplateResolutionError(code, message)`，错误码：`invalid_template`（非法 `$` 语法）、`invalid_root`（`$unknown.` 前缀）、`forbidden_step_field`（`$steps.x.<非result>`）、`missing_step`（引用不存在/未完成的步骤）、`missing_path`（路径不存在）。
- `resolve_input_template(template, *, run_input, run_context, step_results) -> dict`：
  - 递归遍历 dict / list；**整值替换**（字符串恰好等于模板路径才替换，不做字符串内插），非 `$` 开头字符串原样保留；
  - 以 `$` 开头但不匹配白名单语法的字符串一律抛错（fail closed，防注入）；
  - 白名单路径：`$input.<path>`、`$context.<path>`、`$steps.<step_key>.result`、`$steps.<step_key>.result.<path>`；
  - path 段支持字典键和整数列表下标；
  - `step_results` 视图由已完成步骤的 `result["data"]` 构造，引用未完成步骤 → `missing_step`。
- `build_step_view(steps) -> dict[str, Any]`：从 step rows 构造解析视图。

## 2. 新增 `backend/app/services/agent_workflow_runtime.py`（执行循环）

核心入口：

```python
async def run_workflow(db, *, run_id, user_id, max_retries=DEFAULT_STEP_RETRIES) -> AgentWorkflowRun
```

循环逻辑（每轮重新 load run/steps，模板解析均基于最新落库状态）：

1. run 处于终态 → 返回；每轮先 `expire_workflow_run` 检查 deadline。
2. `get_ready_steps` 为空时：run 为 waiting_* → 返回（异步/用户等待，回传归阶段 D）；全部 completed → 返回；否则 `fail_workflow_run(code="workflow_deadlock")`。
3. 取第一个 ready step：
   - **capability 未注册** → `mark_step_running` 后持久化 failed `CapabilityResult`（`unknown_capability`），走 store 既有失败传播；
   - **解析模板**：先解析、成功后随 `mark_step_running(resolved_input=..., idempotency_key=...)` 落库；解析失败 → mark running + persist failed（`template_resolution_failed`），复用同一失败通路；
   - 幂等键：capability 声明 `idempotent=True` 时使用跨 attempt 稳定键 `workflow:{run_id}:{step_key}`（重试时 replay 而非重复写入）。
4. **执行与重试**（关键设计：重试必须在 runtime 内完成，不能"先落失败再 retry_step"——`_fail_run` 会把 pending 依赖步骤置为 cancelled 且不可复活）：
   - attempt 1 起 `mark_step_running`（attempt=1）；对 retryable 失败且次数未耗尽（上限 `1 + max_retries`）：调新增的 `record_step_attempt`（写 `workflow.step.retried` 事件、attempt+=1）后重新执行，**中间失败不落 step.result**；
   - 最终结果（成功或末次失败）→ `persist_step_result`；
   - **超时强制**：`asyncio.wait_for(execute_capability(...), timeout=spec.timeout_seconds)`，`TimeoutError` → 构造 failed `CapabilityResult`（code `capability_timeout`，retryable 继承 spec）；
   - `execute_capability` 调用传入 attempt、user（按 user_id 从 db 查）、conversation_id、message_id。
5. 结果为 `waiting_async` / `waiting_user` → 返回 run。

## 3. store 小幅扩展（`agent_workflow_store.py`，保持其状态机权威地位）

- `record_step_attempt(db, *, run, step, commit=True)`：running 态记录重试尝试（attempt+=1 + `workflow.step.retried` 事件），不迁移状态——供 runtime 内部重试，避免破坏依赖步骤；
- `fail_workflow_run(db, *, run, code, message, detail=None, commit=True)`：把现有私有 `_fail_run` 公开化，供 deadlock 检测使用。

状态机表本身零改动。

## 4. 测试

新增 `backend/tests/test_agent_workflow_templates.py`：
- `$input` / `$context` / `$steps.x.result` 命中与深路径、列表下标、整值替换、非 `$` 字符串透传、嵌套容器；
- 拒绝分支：`$unknown.root`、`$steps.x.error`、`$steps.missing.result`、路径不存在、裸 `$`、畸形路径（fail closed）。

新增 `backend/tests/test_agent_workflow_runtime.py`（沿用 conftest 的 db fixture + 内存 SQLite，monkeypatch 风格参照 `test_agent_capability_registry.py`）：
- **验收用例**：三步 DAG `analyze → search → compose`（compose 用测试内向 `CAPABILITY_REGISTRY` 注入的临时 fake capability，测试后清理），断言第二步 `resolved_input` 确实来自第一步的结构化输出（而非自然语言历史），run 最终 completed、context 三键齐全、事件序列完整；
- 首步失败 → 后续步骤不执行、run failed、依赖步骤 cancelled；
- retryable 失败一次后成功 → attempt 计数正确、依赖步骤仍完成、含 `workflow.step.retried` 事件；
- 重试耗尽 → run failed，error 含最后一次错误；
- 超时（慢 adapter + 小 timeout，monkeypatch spec timeout）→ `capability_timeout`；
- unknown capability、模板解析错误 → run failed 且 error code 正确；
- deadlock：手工构造无 ready 步骤的 running run → `workflow_deadlock`；
- `waiting_user` 提前返回；
- 崩溃恢复：执行中断（step 遗留 running）→ `recover_workflow_run` 后 `run_workflow` 续跑至完成。

回归：`test_agent_workflow_store.py`、`test_agent_capability_registry.py` 全绿；`test_ai_service.py` 按既有基线对比（HEAD 上约 22 个既有失败，不做全绿预期）。

## 5. 收尾

- `.gitignore` 增加 `!backend/app/models/agent_workflow.py`（当前被 `backend/app/models/*` 忽略，提交时会丢模型文件导致 conftest/env.py 导入失败）；
- 迁移不新增（表已在 f9a0b1c2d3e4）；如需验证沿用 stamp+compare 法，不跑全量 `upgrade`（空 SQLite 会在旧迁移处断）。

## 验收标准（文档 §12 阶段 C）

一个三步 workflow 通过 `create_workflow_run` → `run_workflow` 完整运行，不依赖 `send_ai_message` 条件分支；`$input/$context/$steps` 白名单模板、重试、超时、幂等键、deadlock 检测、durable 事件全部落地。
