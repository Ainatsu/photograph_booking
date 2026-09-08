"""Regression coverage for interrupted SQLite batch migrations."""

import importlib.util
import sqlite3
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "w3x4y5z6a7b8_add_ai_conversation_thread_metadata.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("thread_metadata_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_removes_stale_sqlite_batch_table(tmp_path):
    db_path = tmp_path / "interrupted.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql(
            """CREATE TABLE ai_conversations (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title VARCHAR(255),
                created_at DATETIME,
                updated_at DATETIME,
                archived_at DATETIME
            )"""
        )
        connection.exec_driver_sql(
            "CREATE TABLE _alembic_tmp_ai_conversations (id INTEGER PRIMARY KEY)"
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            _load_migration().upgrade()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(ai_conversations)")
        }

    assert "_alembic_tmp_ai_conversations" not in tables
    assert {"status", "last_message_preview", "active_task_id"} <= columns
