"""Assistant = RAG: Retrieve (hybrid search) -> Augment (books as context) -> Generate (LLM).

Retrieve runs two searches and fuses them with Reciprocal Rank Fusion (RRF):
  keyword : Postgres full-text rank + tag overlap  (exact words: "Asimov", "Rome")
  semantic: pgvector cosine distance to the question's embedding  (meaning: "stranded on another planet")
RRF score = sum over lists of 1 / (60 + rank). It needs ranks only, so the two scores never have to be comparable.

If the embedding or chat API fails, we log it and fall back to keyword search + a templated answer,
so the library keeps working without the AI service.
"""
import logging
import re

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, joinedload

from app.ai.provider import AIError, AIProvider, Embedder, NoneProvider, get_embedder, get_provider
from app.models import Book, User
from app.services import activity

log = logging.getLogger(__name__)

STOPWORDS = {"the", "and", "for", "about", "something", "some", "book", "books", "want", "read",
             "like", "with", "any", "can", "you", "suggest", "recommend", "please", "give", "show"}
LIMIT = 6
CANDIDATES = 10
RRF_K = 60
MAX_DISTANCE = 0.75  # cosine distance cut-off: farther than this is "not really related"


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
    stmt = (select(Book).options(joinedload(Book.category)).where(score > 0)
            .order_by(score.desc(), Book.title).limit(limit))
    return list(db.scalars(stmt))


def semantic_search(db: Session, query_vector: list[float], limit: int = CANDIDATES) -> list[Book]:
    distance = Book.embedding.cosine_distance(query_vector)   # pgvector operator <=>
    stmt = (select(Book).options(joinedload(Book.category))
            .where(Book.embedding.is_not(None), distance < MAX_DISTANCE)
            .order_by(distance).limit(limit))
    return list(db.scalars(stmt))


def rrf_merge(ranked_lists: dict[str, list[Book]], limit: int = LIMIT) -> tuple[list[Book], dict[int, list[str]]]:
    """Fuse ranked lists. Returns books in fused order + which search found each book."""
    scores: dict[int, float] = {}
    found_by: dict[int, list[str]] = {}
    books: dict[int, Book] = {}
    for source, items in ranked_lists.items():
        for rank, book in enumerate(items, start=1):
            scores[book.id] = scores.get(book.id, 0.0) + 1.0 / (RRF_K + rank)
            found_by.setdefault(book.id, []).append(source)
            books[book.id] = book
    order = sorted(scores, key=lambda bid: (-scores[bid], books[bid].title))[:limit]
    return [books[i] for i in order], {i: found_by[i] for i in order}


def retrieve(db: Session, question: str, embedder: Embedder) -> tuple[list[Book], dict[int, list[str]], str, str | None]:
    """Returns (books, found_by, retrieval_mode, error)."""
    keyword_hits = search_books(db, question, limit=CANDIDATES)
    if embedder.name == "none":
        books, found_by = rrf_merge({"keyword": keyword_hits})
        return books, found_by, "keyword", None
    try:
        qvec = embedder.embed([question])[0]
    except AIError as e:
        log.warning("semantic retrieval unavailable, using keyword only: %s", e)
        books, found_by = rrf_merge({"keyword": keyword_hits})
        return books, found_by, "keyword", f"Semantic search unavailable: {e}"
    books, found_by = rrf_merge({"semantic": semantic_search(db, qvec), "keyword": keyword_hits})
    return books, found_by, "hybrid", None


def ask(db: Session, user: User, question: str,
        provider: AIProvider | None = None, embedder: Embedder | None = None) -> dict:
    provider = provider or get_provider()
    embedder = embedder or get_embedder()
    books, found_by, mode, error = retrieve(db, question, embedder)

    used = provider.name
    if not books:
        # Nothing retrieved: an LLM would only be tempted to invent books or services. Skip it (and its cost).
        answer, used = NoneProvider().generate(question, books), "none"
    else:
        try:
            answer = provider.generate(question, books)
        except AIError as e:
            log.warning("LLM unavailable, using templated answer: %s", e)
            answer, used = NoneProvider().generate(question, books), "none"
            error = f"{error + '; ' if error else ''}AI answer unavailable: {e}"

    # Books the answer actually names come first; the rest are "other matches" (often keyword noise).
    lowered = answer.lower()
    recommended = [b.id for b in books if b.title.lower() in lowered]
    books = sorted(books, key=lambda b: b.id not in recommended)

    activity.log(db, user.id, "assistant.ask", "assistant", None,
                 question=question[:200], hits=len(books), retrieval=mode, model=used)
    db.commit()
    return {"answer": answer, "books": books, "provider": used, "retrieval": mode,
            "found_by": found_by, "recommended": recommended, "error": error}
