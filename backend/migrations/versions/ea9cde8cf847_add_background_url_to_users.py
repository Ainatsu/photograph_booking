"""add_background_url_to_users

Revision ID: ea9cde8cf847
Revises: 547db93a2ff9
Create Date: 2026-06-23 16:59:41.170147

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea9cde8cf847'
down_revision: Union[str, Sequence[str], None] = '547db93a2ff9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('background_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'background_url')
