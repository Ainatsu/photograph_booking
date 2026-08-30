"""remove hourly photographer availability"""

from alembic import op


revision = "q7r8s9t0u1v2"
down_revision = "p6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("photographer_profiles", "available_hours")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("photographer_profiles", sa.Column("available_hours", sa.JSON(), nullable=True))
