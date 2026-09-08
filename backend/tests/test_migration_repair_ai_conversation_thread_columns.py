"""Regression coverage for databases stamped past incomplete thread DDL."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def test_upgrade_repairs_missing_thread_columns(tmp_path):
    db_path = tmp_path / "missing-thread-columns.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute(
            """CREATE TABLE ai_conversations (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(255),
                created_at DATETIME,
                updated_at DATETIME
            )"""
        )
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute(
            "INSERT INTO alembic_version (version_num) VALUES ('d7e8f9a0b1c2')"
        )

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ai_conversations)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(ai_conversations)")
        }
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert {
        "root_conversation_id",
        "forked_from_conversation_id",
        "fork_boundary",
        "folder_id",
    } <= columns
    assert {
        "ix_ai_conversations_root_conversation_id",
        "ix_ai_conversations_forked_from_conversation_id",
        "ix_ai_conversations_folder_id",
    } <= indexes
    assert version == "e8f9a0b1c2d3"
