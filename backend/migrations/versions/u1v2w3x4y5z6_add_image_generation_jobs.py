"""add image generation jobs and assets

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
"""

from alembic import op
import sqlalchemy as sa


revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_generation_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=False),
        sa.Column("agent_task_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("normalized_prompt", sa.Text(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("usage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["ai_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_image_generation_owner_idempotency"),
    )
    for name, columns in (
        ("ix_image_generation_jobs_owner_id", ["owner_id"]),
        ("ix_image_generation_jobs_conversation_id", ["conversation_id"]),
        ("ix_image_generation_jobs_source_message_id", ["source_message_id"]),
        ("ix_image_generation_jobs_agent_task_id", ["agent_task_id"]),
        ("ix_image_generation_jobs_status", ["status"]),
        ("ix_image_generation_jobs_available_at", ["available_at"]),
        ("ix_image_generation_jobs_status_available", ["status", "available_at"]),
    ):
        op.create_index(name, "image_generation_jobs", columns, unique=False)

    op.create_table(
        "image_generation_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("storage_url", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["image_generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "role", "position", name="uq_image_generation_asset_position"),
    )
    op.create_index("ix_image_generation_assets_job_id", "image_generation_assets", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_image_generation_assets_job_id", table_name="image_generation_assets")
    op.drop_table("image_generation_assets")
    for name in (
        "ix_image_generation_jobs_status_available",
        "ix_image_generation_jobs_available_at",
        "ix_image_generation_jobs_status",
        "ix_image_generation_jobs_agent_task_id",
        "ix_image_generation_jobs_source_message_id",
        "ix_image_generation_jobs_conversation_id",
        "ix_image_generation_jobs_owner_id",
    ):
        op.drop_index(name, table_name="image_generation_jobs")
    op.drop_table("image_generation_jobs")
