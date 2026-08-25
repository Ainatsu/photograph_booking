"""add photographer service coordinates"""

from alembic import op
import sqlalchemy as sa

revision = "j0e1f2a3b4c5"
down_revision = "i9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("photographer_profiles", sa.Column("service_city", sa.String(length=80), nullable=True))
    op.add_column("photographer_profiles", sa.Column("service_address", sa.String(length=255), nullable=True))
    op.add_column("photographer_profiles", sa.Column("service_latitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("photographer_profiles", sa.Column("service_longitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("photographer_profiles", sa.Column("service_radius_km", sa.Integer(), nullable=True))
    op.add_column("photographer_profiles", sa.Column("location_source", sa.String(length=30), nullable=True))


def downgrade() -> None:
    for name in ("location_source", "service_radius_km", "service_longitude", "service_latitude", "service_address", "service_city"):
        op.drop_column("photographer_profiles", name)
