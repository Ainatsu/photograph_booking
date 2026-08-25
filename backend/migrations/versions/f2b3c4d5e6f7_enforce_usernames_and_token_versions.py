"""enforce non-null usernames after identity migration"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(sa.text(
        "SELECT username, count(*) FROM users "
        "WHERE username IS NOT NULL AND trim(username) <> '' "
        "GROUP BY username HAVING count(*) > 1"
    )).fetchall()
    if duplicate:
        raise RuntimeError(f"cannot enforce usernames; duplicates found: {duplicate}")
    missing = bind.execute(sa.text(
        "SELECT id FROM users WHERE username IS NULL OR trim(username) = ''"
    )).fetchall()
    if missing:
        bind.execute(sa.text(
            "UPDATE users SET username = 'user_' || id, username_requires_update = 1 "
            "WHERE username IS NULL OR trim(username) = ''"
        ))
    remaining = bind.execute(sa.text(
        "SELECT id FROM users WHERE username IS NULL OR trim(username) = ''"
    )).fetchall()
    if remaining:
        raise RuntimeError(f"cannot enforce usernames; rows remain without username: {remaining}")

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(24), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(24), nullable=True)
