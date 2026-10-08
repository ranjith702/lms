"""Keep book embeddings in sync with book text.

A book's embedding is valid only for the exact text + model that produced it, so we store a hash of
both. `embed_stale` re-embeds only books whose hash no longer matches (new, edited, or model changed).
"""
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, undefer

from app.ai.provider import AIError, Embedder
from app.models import Book

log = logging.getLogger(__name__)
BATCH = 32


def book_text(book: Book) -> str:
    category = book.category.name if book.category else ""
    return (f"{book.title}. By {book.author}. Category: {category}. "
            f"Topics: {', '.join(book.tags)}. {book.description}")


def text_hash(book: Book, model: str) -> str:
    return hashlib.sha256(f"{model}\n{book_text(book)}".encode()).hexdigest()


def embed_stale(db: Session, embedder: Embedder, only_ids: list[int] | None = None) -> dict:
    """Embed books that are missing or out of date. Returns counts. Raises AIError on API failure."""
    stmt = select(Book).options(joinedload(Book.category), undefer(Book.embedding)).order_by(Book.id)
    if only_ids:
        stmt = stmt.where(Book.id.in_(only_ids))
    books = db.scalars(stmt).all()
    stale = [b for b in books if b.embedding is None or b.embedding_hash != text_hash(b, embedder.name)]
    for i in range(0, len(stale), BATCH):
        chunk = stale[i:i + BATCH]
        vectors = embedder.embed([book_text(b) for b in chunk])
        for book, vec in zip(chunk, vectors):
            book.embedding, book.embedding_model = vec, embedder.name
            book.embedding_hash = text_hash(book, embedder.name)
        db.commit()  # commit per batch: a later rate-limit error keeps earlier progress
    return {"total": len(books), "embedded": len(stale), "up_to_date": len(books) - len(stale)}


def embed_after_change(db: Session, embedder: Embedder, book_ids: int | list[int]) -> None:
    """Best-effort re-embed right after a librarian adds/edits a book (or renames its category).
    If the AI service is down the book is still saved; `python -m scripts.embed_books` catches it up later."""
    if embedder.name == "none":
        return
    ids = [book_ids] if isinstance(book_ids, int) else book_ids
    try:
        embed_stale(db, embedder, only_ids=ids)
    except AIError as e:
        db.rollback()
        log.warning("embedding skipped for books %s: %s", ids, e)
