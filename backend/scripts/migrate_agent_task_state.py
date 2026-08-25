"""Normalize persisted Agent task state after the workspace isolation rollout.

The migration is deliberately conservative: it never deletes durable task data.
It keeps the newest verifiable active task per conversation, pauses older active
rows, and removes legacy conversation-scoped Redis working-memory keys.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def migrate(*, dry_run: bool = False) -> dict[str, int]:
    from backend.app.core.cache import cache_delete_pattern
    from backend.app.core.database import SessionLocal
    from backend.app.models.agent_task_session import AgentTaskSession

    paused = 0
    conversations = 0
    with SessionLocal() as db:
        rows = (
            db.query(AgentTaskSession)
            .filter(AgentTaskSession.status == "active")
            .order_by(AgentTaskSession.conversation_id.asc(), AgentTaskSession.last_active_at.desc())
            .all()
        )
        seen: set[tuple[int, int]] = set()
        for task in rows:
            key = (int(task.user_id), int(task.conversation_id))
            if key not in seen:
                seen.add(key)
                conversations += 1
                continue
            task.status = "paused"
            task.ended_at = task.ended_at or task.last_active_at
            paused += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()

    # Old keys cannot be trusted because they have no task identity. New task
    # workspaces are keyed by task_id and remain untouched.
    if not dry_run:
        cache_delete_pattern("agent:working-memory:*")
    return {"active_conversations": conversations, "paused_duplicates": paused}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(migrate(dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
