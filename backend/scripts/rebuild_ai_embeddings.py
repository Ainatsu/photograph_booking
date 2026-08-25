"""重建 AI 资源文档及文本/图片向量嵌入。"""

import argparse
import json

from backend.app.core.database import SessionLocal
from backend.app.services.ai_embedding_service import sync_resource_embeddings
from backend.app.services.ai_multimodal_embedding_service import sync_resource_image_embeddings
from backend.app.services.ai_resource_index_service import rebuild_ai_resource_documents


def main() -> int:
    """命令行入口：重建资源文档并同步文本与图片嵌入。"""
    parser = argparse.ArgumentParser(description="Rebuild AI resource documents and embeddings")
    parser.add_argument("--owner-user-id", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        document_count = rebuild_ai_resource_documents(
            db,
            owner_user_id=args.owner_user_id,
            sync_embeddings=False,
        )
        result = sync_resource_embeddings(
            db,
            owner_user_id=args.owner_user_id,
            force=args.force,
        )
        image_result = sync_resource_image_embeddings(
            db,
            owner_user_id=args.owner_user_id,
            force=args.force,
        )
        print(json.dumps({
            "documents": document_count,
            "text_embeddings": result.__dict__,
            "image_embeddings": image_result.__dict__,
        }, ensure_ascii=False, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
