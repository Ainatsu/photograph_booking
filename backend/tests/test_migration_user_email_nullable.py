"""迁移回归测试：确保 users.email 的历史 NOT NULL 约束被解除。

注册流程现在写入 ``email = NULL``（可选邮箱先存进 ``pending_email``），
旧库若仍保留 ``NOT NULL`` 会让 IntegrityError 被误报成“用户名或手机号已被使用”。
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 身份重构之前的 users 表形态：email 为 NOT NULL。
LEGACY_USERS_TABLE = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(500),
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN,
    is_admin BOOLEAN,
    is_banned BOOLEAN,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
    updated_at DATETIME,
    background_url VARCHAR(500),
    username VARCHAR(24) NOT NULL,
    username_requires_update BOOLEAN DEFAULT '0' NOT NULL,
    username_changed_at DATETIME,
    pending_email VARCHAR(255),
    email_verified_at DATETIME,
    phone_verified_at DATETIME,
    show_email_on_profile BOOLEAN DEFAULT '0' NOT NULL,
    token_version INTEGER DEFAULT '0' NOT NULL,
    password_changed_at DATETIME,
    PRIMARY KEY (id)
)
"""


def _email_column(db_path: Path) -> sqlite3.Row:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return next(
            row for row in con.execute("PRAGMA table_info(users)") if row["name"] == "email"
        )
    finally:
        con.close()


@pytest.fixture()
def legacy_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "legacy.db"
    con = sqlite3.connect(db_path)
    con.execute(LEGACY_USERS_TABLE)
    con.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    con.execute("CREATE UNIQUE INDEX uq_users_username ON users (username)")
    con.execute("CREATE UNIQUE INDEX uq_users_phone ON users (phone)")
    con.execute("CREATE INDEX ix_users_id ON users (id)")
    con.execute(
        "INSERT INTO users (id, email, hashed_password, display_name, role, username, "
        "username_requires_update, show_email_on_profile, token_version) "
        "VALUES (1, 'legacy@example.com', 'x', '老用户', 'customer', 'legacy_user', 0, 0, 0)"
    )
    con.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    con.execute("INSERT INTO alembic_version (version_num) VALUES ('j0e1f2a3b4c5')")
    con.commit()
    con.close()
    return db_path


def test_upgrade_makes_email_nullable_and_keeps_rows(legacy_db: Path):
    assert _email_column(legacy_db)["notnull"] == 1

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{legacy_db}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    assert _email_column(legacy_db)["notnull"] == 0

    con = sqlite3.connect(legacy_db)
    try:
        assert con.execute("SELECT email FROM users WHERE id = 1").fetchone()[0] == (
            "legacy@example.com"
        )
        # 注册路径写入的行：邮箱为空，可选邮箱落在 pending_email。
        con.execute(
            "INSERT INTO users (email, pending_email, hashed_password, display_name, role, "
            "username, username_requires_update, show_email_on_profile, token_version) "
            "VALUES (NULL, 'pending@example.com', 'x', '新用户', 'customer', 'new_user', 0, 0, 0)"
        )
        con.commit()
        indexes = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'users'"
        )}
        assert {"ix_users_email", "uq_users_username", "uq_users_phone"} <= indexes
    finally:
        con.close()
