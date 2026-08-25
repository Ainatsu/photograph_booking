"""add photographer max booking date

Revision ID: c7d8e9f0a1b2
Revises: f2b3c4d5e6f7
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("photographer_profiles", sa.Column("max_booking_date", sa.Date(), nullable=True))

def downgrade():
    op.drop_column("photographer_profiles", "max_booking_date")
