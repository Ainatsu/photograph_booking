"""add batched inspiration generation persistence

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
"""

from alembic import op
import sqlalchemy as sa


revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspiration_generation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inspiration_id", sa.Integer(), nullable=False),
        sa.Column("agent_task_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("reference_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_images", sa.Integer(), nullable=False),
        sa.Column("completed_images", sa.Integer(), nullable=False),
        sa.Column("failed_images", sa.Integer(), nullable=False),
        sa.Column("summary_result", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inspiration_id"], ["inspirations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspiration_id", name="uq_inspiration_generation_jobs_inspiration"),
    )
    op.create_index("ix_inspiration_generation_jobs_inspiration_id", "inspiration_generation_jobs", ["inspiration_id"], unique=True)
    op.create_index("ix_inspiration_generation_jobs_agent_task_id", "inspiration_generation_jobs", ["agent_task_id"], unique=False)
    op.create_index("ix_inspiration_generation_jobs_owner_id", "inspiration_generation_jobs", ["owner_id"], unique=False)
    op.create_index("ix_inspiration_generation_jobs_conversation_id", "inspiration_generation_jobs", ["conversation_id"], unique=False)
    op.create_index("ix_inspiration_generation_jobs_status", "inspiration_generation_jobs", ["status"], unique=False)
    op.create_index("ix_inspiration_generation_jobs_status_updated", "inspiration_generation_jobs", ["status", "updated_at"], unique=False)

    op.create_table(
        "inspiration_generation_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("attachment_indices", sa.JSON(), nullable=False),
        sa.Column("image_refs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["inspiration_generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "batch_index", name="uq_inspiration_generation_batch_order"),
    )
    op.create_index("ix_inspiration_generation_batches_job_id", "inspiration_generation_batches", ["job_id"], unique=False)
    op.create_index("ix_inspiration_generation_batches_status", "inspiration_generation_batches", ["status"], unique=False)
    op.create_index("ix_inspiration_generation_batches_available_at", "inspiration_generation_batches", ["available_at"], unique=False)
    op.create_index("ix_inspiration_generation_batches_status_available", "inspiration_generation_batches", ["status", "available_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_inspiration_generation_batches_status_available", table_name="inspiration_generation_batches")
    op.drop_index("ix_inspiration_generation_batches_available_at", table_name="inspiration_generation_batches")
    op.drop_index("ix_inspiration_generation_batches_status", table_name="inspiration_generation_batches")
    op.drop_index("ix_inspiration_generation_batches_job_id", table_name="inspiration_generation_batches")
    op.drop_table("inspiration_generation_batches")
    op.drop_index("ix_inspiration_generation_jobs_status_updated", table_name="inspiration_generation_jobs")
    op.drop_index("ix_inspiration_generation_jobs_status", table_name="inspiration_generation_jobs")
    op.drop_index("ix_inspiration_generation_jobs_conversation_id", table_name="inspiration_generation_jobs")
    op.drop_index("ix_inspiration_generation_jobs_owner_id", table_name="inspiration_generation_jobs")
    op.drop_index("ix_inspiration_generation_jobs_agent_task_id", table_name="inspiration_generation_jobs")
    op.drop_index("ix_inspiration_generation_jobs_inspiration_id", table_name="inspiration_generation_jobs")
    op.drop_table("inspiration_generation_jobs")
