"""add favorite_type and package fields

Revision ID: d8f1a2b3c4e5
Revises: 65cceb5feedc
Create Date: 2026-06-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f1a2b3c4e5'
down_revision: Union[str, Sequence[str], None] = '65cceb5feedc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN directly; use batch_alter_table
    with op.batch_alter_table('favorites') as batch_op:
        batch_op.alter_column('work_id', existing_type=sa.String(64), nullable=True)
        batch_op.add_column(sa.Column('favorite_type', sa.String(16), nullable=True))
        batch_op.add_column(sa.Column('package_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('package_data', sa.JSON(), nullable=True))
        batch_op.create_unique_constraint('uq_favorite_user_package', ['user_id', 'package_id'])

    # Backfill existing rows
    op.execute("UPDATE favorites SET favorite_type = 'work' WHERE favorite_type IS NULL")

    with op.batch_alter_table('favorites') as batch_op:
        batch_op.alter_column('favorite_type', existing_type=sa.String(16), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('favorites') as batch_op:
        batch_op.alter_column('favorite_type', existing_type=sa.String(16), nullable=True)
        batch_op.drop_constraint('uq_favorite_user_package', type_='unique')
        batch_op.drop_column('package_data')
        batch_op.drop_column('package_id')
        batch_op.drop_column('favorite_type')

    # Remove rows where work_id is NULL before making it non-nullable
    op.execute("DELETE FROM favorites WHERE work_id IS NULL")

    with op.batch_alter_table('favorites') as batch_op:
        batch_op.alter_column('work_id', existing_type=sa.String(64), nullable=False)
