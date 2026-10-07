"""Assistant = Retrieve (Postgres search) + Generate (AIProvider).

This is the "R" and "G" of RAG. Retrieval today is keyword based: Postgres full-text
rank over title/author/description, plus tag overlap. Phase 2 swaps retrieval for
embeddings (pgvector) - the generate step and the API stay the same.
"""
import re

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.models import Book, User
from app.services import activity

STOPWORDS = {"the", "and", "for", "about", "something", "some", "book", "books", "want", "read",
             "like", "with", "any", "can", "you", "suggest", "recommend", "please", "give", "show"}
LIMIT = 6

def keywords(text: str) -> list[str]:
    # Only [a-z0-9] words survive -> nothing can break the tsquery syntax.
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS]


def search_books(db: Session, text: str, limit: int = LIMIT) -> list[Book]:
    words = keywords(text)
    if not words:
        return []
    # Built from SQLAlchemy expressions, so every value is a bound parameter (no SQL injection).
    text_rank = func.ts_rank(Book.search, func.to_tsquery("english", " | ".join(words)))
    tag_hits = sum(cast(Book.tags.any(w), Integer) for w in words)  # tags are stored lowercase
    score = text_rank + 0.3 * tag_hits
    stmt = select(Book).where(score > 0).order_by(score.desc(), Book.title).limit(limit)
    return list(db.scalars(stmt))


def ask(db: Session, user: User, question: str) -> dict:
    books = search_books(db, question)
    provider = get_provider()
    answer = provider.generate(question, books)
    activity.log(db, user.id, "assistant.ask", "assistant", None, question=question[:200], hits=len(books))
    db.commit()
    return {"answer": answer, "books": books, "provider": provider.name}
