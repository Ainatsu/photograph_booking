"""add agent workflow runs/steps/events

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
"""

from alembic import op
import sqlalchemy as sa

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_workflow_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("ai_messages.id"), nullable=True),
        sa.Column("workflow_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("planner_revision", sa.Integer(), nullable=False),
        sa.Column("current_step_id", sa.String(length=36), nullable=True),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_workflow_runs_user_id", "agent_workflow_runs", ["user_id"])
    op.create_index("ix_agent_workflow_runs_conversation_id", "agent_workflow_runs", ["conversation_id"])
    op.create_index("ix_agent_workflow_runs_message_id", "agent_workflow_runs", ["message_id"])
    op.create_index("ix_agent_workflow_runs_workflow_type", "agent_workflow_runs", ["workflow_type"])
    op.create_index("ix_agent_workflow_runs_status", "agent_workflow_runs", ["status"])
    op.create_index("ix_agent_workflow_runs_user_status", "agent_workflow_runs", ["user_id", "status"])
    op.create_index("ix_agent_workflow_runs_conversation_status", "agent_workflow_runs", ["conversation_id", "status"])

    op.create_table(
        "agent_workflow_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(length=36), sa.ForeignKey("agent_workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=128), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("input_template", sa.JSON(), nullable=False),
        sa.Column("context_key", sa.String(length=64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("resolved_input", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workflow_run_id", "step_key", name="uq_agent_workflow_step_key"),
    )
    op.create_index("ix_agent_workflow_steps_workflow_run_id", "agent_workflow_steps", ["workflow_run_id"])
    op.create_index("ix_agent_workflow_steps_status", "agent_workflow_steps", ["status"])
    op.create_index("ix_agent_workflow_steps_idempotency_key", "agent_workflow_steps", ["idempotency_key"])
    op.create_index("ix_agent_workflow_steps_run_status", "agent_workflow_steps", ["workflow_run_id", "status"])
    op.create_index("ix_agent_workflow_steps_run_position", "agent_workflow_steps", ["workflow_run_id", "position"])

    op.create_table(
        "agent_workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workflow_run_id", sa.String(length=36), sa.ForeignKey("agent_workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_run_id", "sequence", name="uq_agent_workflow_event_sequence"),
    )
    op.create_index("ix_agent_workflow_events_workflow_run_id", "agent_workflow_events", ["workflow_run_id"])
    op.create_index("ix_agent_workflow_events_step_id", "agent_workflow_events", ["step_id"])
    op.create_index("ix_agent_workflow_events_event_type", "agent_workflow_events", ["event_type"])
    op.create_index("ix_agent_workflow_events_run_id", "agent_workflow_events", ["workflow_run_id", "id"])


def downgrade() -> None:
    op.drop_table("agent_workflow_events")
    op.drop_table("agent_workflow_steps")
    op.drop_table("agent_workflow_runs")
