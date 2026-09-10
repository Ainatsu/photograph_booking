"""Agent Workflow 通用任务计划契约（workflow 阶段 B）。

将阶段 A 的 capability_result_v1 与文档 §6 的 agent_workflow_plan_v2 计划协议
连接起来：计划只声明步骤、依赖与输入模板；状态迁移、权限、deadline 和恢复
由 agent_workflow_store 强制执行，执行入口归阶段 C 的 Runtime。

与旧 agent_task_sequence_v1 的关系：TaskPlan 继续服务固定 search_then_inspire
流程，本契约承载任意依赖图，二者并行不互相迁移。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WORKFLOW_PLAN_SCHEMA_VERSION = "agent_workflow_plan_v2"
WORKFLOW_RUN_SNAPSHOT_SCHEMA_VERSION = "agent_workflow_run_snapshot_v1"

WorkflowRunStatus = Literal[
    "running", "waiting_async", "waiting_user", "completed", "failed", "cancelled"
]
WorkflowStepStatus = Literal[
    "pending", "ready", "running", "waiting_async", "waiting_user", "completed", "failed", "cancelled"
]

TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
TERMINAL_STEP_STATUSES = frozenset({"completed", "failed", "cancelled"})

DEFAULT_MAX_STEPS = 32
HARD_MAX_STEPS = 64

# ── 事件类型（文档 §10；扩展了 recovered / retried / resumed 三类恢复与重试事件）──

WORKFLOW_EVENT_CREATED = "workflow.created"
WORKFLOW_EVENT_STEP_STARTED = "workflow.step.started"
WORKFLOW_EVENT_STEP_COMPLETED = "workflow.step.completed"
WORKFLOW_EVENT_STEP_FAILED = "workflow.step.failed"
WORKFLOW_EVENT_STEP_WAITING_ASYNC = "workflow.step.waiting_async"
WORKFLOW_EVENT_WAITING_USER = "workflow.waiting_user"
WORKFLOW_EVENT_STEP_RETRIED = "workflow.step.retried"
WORKFLOW_EVENT_STEP_RESUMED = "workflow.step.resumed"
WORKFLOW_EVENT_STEP_RECOVERED = "workflow.step.recovered"
WORKFLOW_EVENT_RECOVERED = "workflow.recovered"
WORKFLOW_EVENT_COMPLETED = "workflow.completed"
WORKFLOW_EVENT_FAILED = "workflow.failed"
WORKFLOW_EVENT_CANCELLED = "workflow.cancelled"


class WorkflowStepSpec(BaseModel):
    """计划中的一个步骤声明。

    context_key 是结果合并进 run.context 的键，缺省等于步骤 id；
    文档 §9 的示例里 analyze 步骤的结果落在 $context.image_analysis 下，
    即通过该字段声明，而非硬编码命名规则。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    capability: str = Field(min_length=1, max_length=128)
    depends_on: list[str] = Field(default_factory=list)
    input_template: dict[str, Any] = Field(default_factory=dict)
    context_key: str | None = Field(default=None, min_length=1, max_length=64)

    @property
    def effective_context_key(self) -> str:
        """结果写入 run.context 时使用的键。"""
        return self.context_key or self.id


class WorkflowPlan(BaseModel):
    """通用任务计划 agent_workflow_plan_v2。

    计划校验只保证结构合法（唯一 id、依赖存在、无环）；capability 是否已
    注册由 Runtime 执行时通过 capability registry 强制，本契约不绑定。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent_workflow_plan_v2"] = WORKFLOW_PLAN_SCHEMA_VERSION
    workflow_type: str = Field(min_length=1, max_length=64)
    steps: list[WorkflowStepSpec] = Field(min_length=1, max_length=HARD_MAX_STEPS)

    @model_validator(mode="after")
    def validate_dag(self) -> "WorkflowPlan":
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate_step_id")
        id_set = set(step_ids)
        for step in self.steps:
            if step.id in step.depends_on:
                raise ValueError(f"self_dependency:{step.id}")
            unknown = [dep for dep in step.depends_on if dep not in id_set]
            if unknown:
                raise ValueError(f"unknown_dependency:{step.id}:{','.join(unknown)}")
        _assert_acyclic(self.steps)
        return self

    def step_map(self) -> dict[str, WorkflowStepSpec]:
        return {step.id: step for step in self.steps}


def _assert_acyclic(steps: list[WorkflowStepSpec]) -> None:
    """Kahn 拓扑排序检测环。"""
    spec_map = {step.id: step for step in steps}
    indegree = {step.id: len(set(step.depends_on)) for step in steps}
    dependents: dict[str, list[str]] = {step.id: [] for step in steps}
    for step in steps:
        for dep in set(step.depends_on):
            dependents[dep].append(step.id)
    queue = [step_id for step_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in dependents[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(steps):
        raise ValueError("cyclic_dependencies")
