"""merge existing migration branches

Revision ID: d0e1f2a3b4c5
Revises: c7d8e9f0a1b2, f8a9b0c1d2e3
"""
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = ("c7d8e9f0a1b2", "f8a9b0c1d2e3")
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
