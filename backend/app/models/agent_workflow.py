"""Agent Workflow Runtime 的持久化模型（workflow 阶段 B）。

三张表的职责边界（见 docs/agent-workflow-orchestration-implementation.md §5）：
- AgentWorkflowRun：通用编排的权威状态（context、deadline、当前步骤指针）；
- AgentWorkflowStep：单个 capability 步骤的输入模板、解析结果与状态；
- AgentWorkflowEvent：按 run 递增 sequence 的 durable 事件流，供审计与恢复。

AgentTaskDraft 仍负责用户可编辑的任务表单，不承载通用 DAG 状态。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.core.database import Base


class AgentWorkflowRun(Base):
    """一次 workflow 执行的权威状态。"""

    __tablename__ = "agent_workflow_runs"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("ai_messages.id"), nullable=True, index=True)
    workflow_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="running", index=True)
    # 运行级输入，供 $input.* 模板解析使用。
    input = Column(JSON, nullable=False, default=dict)
    # 已完成步骤的结构化输出按 context_key 合并到这里，供后续步骤读取。
    context = Column(JSON, nullable=False, default=dict)
    # run 完成时最后一个完成步骤（通常为 compose）的 capability_result_v1 信封。
    result = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    planner_revision = Column(Integer, nullable=False, default=0)
    current_step_id = Column(String(36), nullable=True)
    max_steps = Column(Integer, nullable=False, default=32)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_agent_workflow_runs_user_status", "user_id", "status"),
        Index("ix_agent_workflow_runs_conversation_status", "conversation_id", "status"),
    )


class AgentWorkflowStep(Base):
    """workflow 中的一个 capability 步骤。"""

    __tablename__ = "agent_workflow_steps"

    id = Column(String(36), primary_key=True)
    workflow_run_id = Column(String(36), ForeignKey("agent_workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    # 计划内的步骤标识，模板引用 $steps.<step_key>.result 使用它。
    step_key = Column(String(64), nullable=False)
    capability = Column(String(128), nullable=False)
    depends_on = Column(JSON, nullable=False, default=list)
    input_template = Column(JSON, nullable=False, default=dict)
    # 结果合并进 run.context 时使用的键，缺省等于 step_key。
    context_key = Column(String(64), nullable=True)
    # 计划内顺序，保证 ready step 选择与快照输出的确定性。
    position = Column(Integer, nullable=False, default=0)
    resolved_input = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    result = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("workflow_run_id", "step_key", name="uq_agent_workflow_step_key"),
        Index("ix_agent_workflow_steps_run_status", "workflow_run_id", "status"),
        Index("ix_agent_workflow_steps_run_position", "workflow_run_id", "position"),
    )


class AgentWorkflowEvent(Base):
    """按 run 递增 sequence 的 durable workflow 事件。"""

    __tablename__ = "agent_workflow_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_run_id = Column(String(36), ForeignKey("agent_workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("workflow_run_id", "sequence", name="uq_agent_workflow_event_sequence"),
        Index("ix_agent_workflow_events_run_id", "workflow_run_id", "id"),
    )
