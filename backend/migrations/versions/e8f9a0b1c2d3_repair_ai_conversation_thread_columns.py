"""Repair thread lineage columns missing from already-versioned SQLite databases.

Some databases were stamped past the original thread metadata migration after
an interrupted SQLite batch DDL operation.  This migration is intentionally
idempotent so startup upgrades can repair those databases safely.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("ai_conversations"):
        return

    existing = {column["name"] for column in inspector.get_columns("ai_conversations")}
    missing = (
        ("root_conversation_id", sa.Integer()),
        ("forked_from_conversation_id", sa.Integer()),
        ("fork_boundary", sa.String(64)),
        ("folder_id", sa.Integer()),
    )
    if any(name not in existing for name, _ in missing):
        with op.batch_alter_table("ai_conversations") as batch:
            for name, column_type in missing:
                if name in existing:
                    continue
                batch.add_column(sa.Column(name, column_type, nullable=True))

    indexes = {index["name"] for index in inspect(bind).get_indexes("ai_conversations")}
    for name, column in (
        ("ix_ai_conversations_root_conversation_id", "root_conversation_id"),
        ("ix_ai_conversations_forked_from_conversation_id", "forked_from_conversation_id"),
        ("ix_ai_conversations_folder_id", "folder_id"),
    ):
        if column in existing or any(item[0] == column for item in missing):
            if name not in indexes:
                op.create_index(name, "ai_conversations", [column])


def downgrade() -> None:
    # Keep this repair migration non-destructive; older application versions
    # can continue to read the repaired schema.
    pass
