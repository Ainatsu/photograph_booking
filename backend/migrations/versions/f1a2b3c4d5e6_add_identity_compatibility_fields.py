"""add nullable identity fields and verification challenges

This is the additive/backfill half of the identity refactor.  It deliberately
keeps ``users.username`` nullable; the strict non-null cutover belongs to a
later migration after all deployments have been upgraded.
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


USER_COLUMNS = {
    "username": sa.Column("username", sa.String(24), nullable=True),
    "username_requires_update": sa.Column("username_requires_update", sa.Boolean(), nullable=False, server_default="0"),
    "username_changed_at": sa.Column("username_changed_at", sa.DateTime(timezone=True), nullable=True),
    "pending_email": sa.Column("pending_email", sa.String(255), nullable=True),
    "email_verified_at": sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    "phone_verified_at": sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    "show_email_on_profile": sa.Column("show_email_on_profile", sa.Boolean(), nullable=False, server_default="0"),
    "token_version": sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    "password_changed_at": sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
}


def _index_names(bind, table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_columns("users")}
    missing = [column for name, column in USER_COLUMNS.items() if name not in existing]
    if missing:
        with op.batch_alter_table("users") as batch:
            for column in missing:
                batch.add_column(column)

    # Normalize legacy email values before adding/validating uniqueness.  A
    # duplicate normalized value aborts the migration rather than silently
    # selecting an account.
    duplicate_emails = bind.execute(sa.text(
        "SELECT lower(trim(email)) AS value, count(*) AS count "
        "FROM users WHERE email IS NOT NULL AND trim(email) <> '' "
        "GROUP BY lower(trim(email)) HAVING count(*) > 1"
    )).fetchall()
    if duplicate_emails:
        raise RuntimeError(f"identity migration aborted: duplicate normalized emails: {duplicate_emails}")
    # Empty legacy phone strings are semantically missing and must become NULL
    # before the nullable unique index is created.
    bind.execute(sa.text("UPDATE users SET phone = NULL WHERE phone IS NOT NULL AND trim(phone) = ''"))
    duplicate_phones = bind.execute(sa.text(
        "SELECT trim(phone) AS value, count(*) AS count "
        "FROM users WHERE phone IS NOT NULL AND trim(phone) <> '' "
        "GROUP BY trim(phone) HAVING count(*) > 1"
    )).fetchall()
    if duplicate_phones:
        raise RuntimeError(f"identity migration aborted: duplicate phone values: {duplicate_phones}")
    bind.execute(sa.text("UPDATE users SET email = lower(trim(email)) WHERE email IS NOT NULL"))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind.execute(sa.text(
        "UPDATE users SET username = 'user_' || id, username_requires_update = 1 "
        "WHERE username IS NULL OR trim(username) = ''"
    ))
    bind.execute(sa.text(
        "UPDATE users SET email_verified_at = :now "
        "WHERE email IS NOT NULL AND trim(email) <> '' AND email_verified_at IS NULL"
    ), {"now": now})

    indexes = _index_names(bind, "users")
    if "uq_users_username" not in indexes:
        op.create_index("uq_users_username", "users", ["username"], unique=True)
    if "uq_users_phone" not in indexes:
        # SQLite and PostgreSQL both allow multiple NULLs in a unique index.
        op.create_index("uq_users_phone", "users", ["phone"], unique=True)

    if "identity_verification_challenges" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "identity_verification_challenges",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("channel", sa.String(10), nullable=False),
            sa.Column("target", sa.String(255), nullable=False),
            sa.Column("purpose", sa.String(32), nullable=False),
            sa.Column("code_hash", sa.String(64), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("request_ip", sa.String(45), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    for name, columns in [
        ("ix_identity_challenges_channel", ["channel"]),
        ("ix_identity_challenges_target", ["target"]),
        ("ix_identity_challenges_purpose", ["purpose"]),
        ("ix_identity_challenges_user_id", ["user_id"]),
    ]:
        if name not in _index_names(bind, "identity_verification_challenges"):
            op.create_index(name, "identity_verification_challenges", columns)


def downgrade() -> None:
    op.drop_table("identity_verification_challenges")
    op.drop_index("uq_users_phone", table_name="users")
    op.drop_index("uq_users_username", table_name="users")
    with op.batch_alter_table("users") as batch:
        for name in reversed(list(USER_COLUMNS)):
            batch.drop_column(name)
