"""同步平台规则文档到 RAG 资源库并生成向量嵌入。"""

import argparse
import json

from backend.app.core.database import SessionLocal
from backend.app.services.platform_rule_service import sync_platform_rules


def main() -> int:
    """命令行入口：切分 docs/rules 并同步规则文档与向量嵌入。"""
    parser = argparse.ArgumentParser(description="Sync platform rule documents into the RAG store")
    parser.add_argument("--force", action="store_true", help="内容未变化时也重新生成向量")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = sync_platform_rules(db, force=args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
