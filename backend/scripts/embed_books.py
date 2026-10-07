"""Compute embeddings for books that are new, edited, or embedded with a different model.

Usage (from backend/):  python -m scripts.embed_books
Needs LMS_AI_PROVIDER=openrouter and LMS_OPENROUTER_API_KEY in .env. Safe to re-run: up-to-date books are skipped.
"""
import sys
import time

from app.ai.provider import AIError, get_embedder
from app.db import SessionLocal
from app.services.embedding_service import embed_stale


def main() -> int:
    embedder = get_embedder()
    if embedder.name == "none":
        print("LMS_AI_PROVIDER=none: set LMS_AI_PROVIDER=openrouter in .env to compute embeddings.")
        return 1
    start = time.perf_counter()
    with SessionLocal() as db:
        try:
            result = embed_stale(db, embedder)
        except AIError as e:
            print(f"Embedding failed: {e}\nBooks embedded before the failure were saved; re-run to continue.")
            return 1
    print(f"Model {embedder.name}: {result['embedded']} embedded, {result['up_to_date']} already up to date "
          f"({result['total']} books) in {time.perf_counter() - start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
