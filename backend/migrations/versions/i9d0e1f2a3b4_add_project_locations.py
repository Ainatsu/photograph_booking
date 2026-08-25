"""add structured project locations

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
"""

from alembic import op
import sqlalchemy as sa


revision = "i9d0e1f2a3b4"
down_revision = "h8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shoot_projects", sa.Column("location_name", sa.String(length=120), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_address", sa.String(length=255), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_latitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_longitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_place_id", sa.String(length=160), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_provider", sa.String(length=30), nullable=True))
    op.add_column("shoot_projects", sa.Column("coordinate_system", sa.String(length=20), nullable=True))
    op.add_column("shoot_projects", sa.Column("location_precision", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("shoot_projects", "location_precision")
    op.drop_column("shoot_projects", "coordinate_system")
    op.drop_column("shoot_projects", "location_provider")
    op.drop_column("shoot_projects", "location_place_id")
    op.drop_column("shoot_projects", "location_longitude")
    op.drop_column("shoot_projects", "location_latitude")
    op.drop_column("shoot_projects", "location_address")
    op.drop_column("shoot_projects", "location_name")
