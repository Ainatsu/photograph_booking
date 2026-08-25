"""make users.email nullable

The identity refactor moved registration to username + verified phone, so a new
account is inserted with ``email = NULL`` and the optional address parked in
``pending_email``.  The additive migration (f1a2b3c4d5e6) never relaxed the
legacy ``NOT NULL`` on ``users.email``, so already-migrated databases rejected
every registration with ``NOT NULL constraint failed: users.email``.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2a3b4c5"
branch_labels = None
depends_on = None


def _email_is_nullable(bind) -> bool:
    for column in sa.inspect(bind).get_columns("users"):
        if column["name"] == "email":
            return bool(column["nullable"])
    raise RuntimeError("users.email column is missing")


def upgrade() -> None:
    bind = op.get_bind()
    if _email_is_nullable(bind):
        return
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "email",
            existing_type=sa.String(255),
            nullable=True,
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Rows created after the identity refactor legitimately have no verified
    # email, so restoring NOT NULL would corrupt them; refuse instead.
    missing = bind.execute(sa.text(
        "SELECT count(*) FROM users WHERE email IS NULL"
    )).scalar()
    if missing:
        raise RuntimeError(
            f"cannot restore NOT NULL on users.email; {missing} row(s) have no email"
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "email",
            existing_type=sa.String(255),
            nullable=False,
            existing_nullable=True,
        )
