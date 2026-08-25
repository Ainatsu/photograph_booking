"""Rebuild native image embeddings for portfolio resources."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hf-endpoint",
        default=os.getenv("HF_ENDPOINT") or "https://hf-mirror.com",
        help="Hugging Face endpoint used to download the SigLIP model.",
    )
    parser.add_argument(
        "--owner-user-id",
        type=int,
        default=None,
        help="Only index one photographer when provided.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed rows even when the image hash is unchanged.",
    )
    args = parser.parse_args()

    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint

    from backend.app.core.database import SessionLocal
    from backend.app.services.ai_multimodal_embedding_service import (
        sync_resource_image_embeddings,
    )

    with SessionLocal() as db:
        result = sync_resource_image_embeddings(
            db,
            owner_user_id=args.owner_user_id,
            force=args.force,
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
