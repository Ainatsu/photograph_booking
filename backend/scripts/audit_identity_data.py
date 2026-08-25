"""Read-only Phase A identity audit.

Usage: ``python -m backend.scripts.audit_identity_data [database-url]``
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import settings


def audit(url: str) -> dict:
    """审计指定数据库 users 表，返回缺失用户名、重复邮箱/电话等检查结果。"""
    engine = create_engine(url)
    with engine.connect() as conn:
        columns = {column["name"] for column in inspect(conn).get_columns("users")}
        selected = [name for name in ("id", "email", "phone", "username") if name in columns]
        rows = conn.execute(text(f"SELECT {', '.join(selected)} FROM users ORDER BY id")).mappings().all()
    emails: dict[str, list[int]] = defaultdict(list)
    phones: dict[str, list[int]] = defaultdict(list)
    missing_usernames = []
    for row in rows:
        if row["email"] and row["email"].strip():
            emails[row["email"].strip().lower()].append(row["id"])
        if row["phone"] and row["phone"].strip():
            phones[row["phone"].strip()].append(row["id"])
        if "username" not in row or not row["username"] or not row["username"].strip():
            missing_usernames.append(row["id"])
    return {
        "database": url,
        "user_count": len(rows),
        "missing_usernames": missing_usernames,
        "duplicate_normalized_emails": {k: v for k, v in emails.items() if len(v) > 1},
        "duplicate_phone_values": {k: v for k, v in phones.items() if len(v) > 1},
        "blank_email_user_ids": [r["id"] for r in rows if r.get("email") is not None and not r["email"].strip()],
        "blank_phone_user_ids": [r["id"] for r in rows if r.get("phone") is not None and not r["phone"].strip()],
    }


if __name__ == "__main__":
    print(json.dumps(audit(sys.argv[1] if len(sys.argv) > 1 else settings.DATABASE_URL), ensure_ascii=False, indent=2))
