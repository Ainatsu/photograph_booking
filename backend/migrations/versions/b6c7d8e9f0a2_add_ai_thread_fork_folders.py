"""add thread fork lineage, folders and task links

Revision ID: b6c7d8e9f0a2
Revises: z5a6b7c8d9e0
"""
from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a2"
down_revision = "z5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation_folders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_ai_conversation_folder_user_name"),
    )
    op.create_index("ix_ai_conversation_folders_user_id", "ai_conversation_folders", ["user_id"])
    op.create_table(
        "ai_conversation_task_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_task_id", sa.String(36), nullable=False),
        sa.Column("target_task_id", sa.String(36), nullable=False),
        sa.Column("source_conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("target_conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for name, cols in (
        ("ix_ai_conversation_task_links_source_task_id", ["source_task_id"]),
        ("ix_ai_conversation_task_links_target_task_id", ["target_task_id"]),
        ("ix_ai_conversation_task_links_source_conversation_id", ["source_conversation_id"]),
        ("ix_ai_conversation_task_links_target_conversation_id", ["target_conversation_id"]),
        ("ix_ai_conversation_task_links_user_id", ["user_id"]),
    ):
        op.create_index(name, "ai_conversation_task_links", cols)
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(sa.Column("root_conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=True))
        batch_op.add_column(sa.Column("forked_from_conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id"), nullable=True))
        batch_op.add_column(sa.Column("fork_boundary", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("folder_id", sa.Integer(), sa.ForeignKey("ai_conversation_folders.id"), nullable=True))
        batch_op.create_index("ix_ai_conversations_root_conversation_id", ["root_conversation_id"])
        batch_op.create_index("ix_ai_conversations_forked_from_conversation_id", ["forked_from_conversation_id"])
        batch_op.create_index("ix_ai_conversations_folder_id", ["folder_id"])


def downgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_index("ix_ai_conversations_folder_id")
        batch_op.drop_index("ix_ai_conversations_forked_from_conversation_id")
        batch_op.drop_index("ix_ai_conversations_root_conversation_id")
        batch_op.drop_column("folder_id")
        batch_op.drop_column("fork_boundary")
        batch_op.drop_column("forked_from_conversation_id")
        batch_op.drop_column("root_conversation_id")
    op.drop_table("ai_conversation_task_links")
    op.drop_table("ai_conversation_folders")
