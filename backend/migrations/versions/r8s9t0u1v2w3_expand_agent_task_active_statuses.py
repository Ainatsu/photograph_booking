"""expand active statuses for inspiration agent tasks"""

from alembic import op
import sqlalchemy as sa


revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


OLD_STATUSES = ("collecting", "editing_page", "submitting")
NEW_STATUSES = (*OLD_STATUSES, "generating", "awaiting_location", "saving", "failed")


def _where(statuses: tuple[str, ...]):
    return sa.text("status IN (" + ", ".join(f"'{status}'" for status in statuses) + ")")


def _drop_active_index_if_exists() -> None:
    bind = op.get_bind()
    indexes = sa.inspect(bind).get_indexes("agent_task_drafts")
    if any(index["name"] == "uq_agent_task_drafts_active_conversation" for index in indexes):
        op.drop_index("uq_agent_task_drafts_active_conversation", table_name="agent_task_drafts")


def upgrade() -> None:
    _drop_active_index_if_exists()
    op.create_index(
        "uq_agent_task_drafts_active_conversation",
        "agent_task_drafts",
        ["conversation_id"],
        unique=True,
        sqlite_where=_where(NEW_STATUSES),
        postgresql_where=_where(NEW_STATUSES),
    )


def downgrade() -> None:
    _drop_active_index_if_exists()
    op.create_index(
        "uq_agent_task_drafts_active_conversation",
        "agent_task_drafts",
        ["conversation_id"],
        unique=True,
        sqlite_where=_where(OLD_STATUSES),
        postgresql_where=_where(OLD_STATUSES),
    )
