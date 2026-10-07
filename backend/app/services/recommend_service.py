"""Rule-based recommendations (no ML yet). Each pick carries a human-readable reason.

Sections:
  close_in_meaning - nearest books by embedding (semantic) to ones you read; needs embeddings
  same_topic    - same category as books you read
  similar       - shares tags / author with books you read (ranked by overlap)
  also_borrowed - "readers who borrowed X also borrowed Y" (co-borrow counts)
  different     - most popular book from categories you have never tried
  popular       - fallback for brand-new readers

Done in Python over the whole catalog: fine for hundreds of books. At ~10k+ books
move the scoring into SQL or swap in embeddings (phase 2).
"""
import math
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Book, Loan

PER_SECTION = 6
COUNTED = ("borrowed", "returned", "pending")


def _popularity(db: Session) -> Counter:
    rows = db.execute(
        select(Loan.book_id, func.count()).where(Loan.status.in_(COUNTED)).group_by(Loan.book_id)
    ).all()
    return Counter(dict(rows))


def _pick(book: Book, reason: str) -> dict:
    return {"book": book, "reason": reason}


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


MIN_SIMILARITY = 0.35


def _close_in_meaning(db: Session, read_ids: set[int], unread: list[Book]) -> list[tuple[Book, str]]:
    """Semantic neighbours: for each unread book, its best cosine match among the books you read.
    Uses stored embeddings only (no API call), so it's free and fast. Empty if books aren't embedded yet."""
    rows = db.execute(select(Book.id, Book.title, Book.embedding).where(Book.embedding.is_not(None))).all()
    vectors = {bid: (title, list(vec)) for bid, title, vec in rows}
    read_vecs = [(vectors[i][0], vectors[i][1]) for i in read_ids if i in vectors]
    if not read_vecs:
        return []
    scored = []
    for b in unread:
        if b.id not in vectors:
            continue
        sim, closest = max((_cosine(vectors[b.id][1], v), t) for t, v in read_vecs)
        if sim >= MIN_SIMILARITY:
            scored.append((sim, b, f"Close in meaning to “{closest}”"))
    return [(b, r) for _, b, r in sorted(scored, key=lambda x: -x[0])]


def for_student(db: Session, user_id: int) -> dict[str, list[dict]]:
    books = db.scalars(select(Book).options(joinedload(Book.category))).all()
    by_id = {b.id: b for b in books}
    pop = _popularity(db)
    read_ids = set(db.scalars(
        select(Loan.book_id).where(Loan.user_id == user_id, Loan.status.in_(COUNTED))
    ).all())
    unread = [b for b in books if b.id not in read_ids]
    rank = lambda b: (-pop[b.id], -b.available_copies, b.title)  # noqa: E731

    if not read_ids:
        return {"popular": [_pick(b, f"Borrowed {pop[b.id]} time(s) by other readers" if pop[b.id] else "Staff pick")
                            for b in sorted(unread, key=rank)[:PER_SECTION]],
                "close_in_meaning": [], "same_topic": [], "similar": [], "also_borrowed": [], "different": []}

    read = [by_id[i] for i in read_ids]
    read_cats = {b.category_id for b in read}
    read_tags = Counter(t for b in read for t in b.tags)
    read_authors = {b.author for b in read}
    used: set[int] = set()

    def take(candidates):
        out = []
        for b, reason in candidates:
            if b.id not in used and len(out) < PER_SECTION:
                used.add(b.id)
                out.append(_pick(b, reason))
        return out

    # close in meaning (embeddings) claims first: it's the strongest signal when available
    close = take(_close_in_meaning(db, read_ids, unread))

    # similar: tag + author overlap, best match first
    scored = []
    for b in unread:
        shared = [t for t in b.tags if t in read_tags]
        score = len(shared) + (2 if b.author in read_authors else 0)
        if score:
            why = []
            if b.author in read_authors:
                why.append(f"more by {b.author}")
            if shared:
                why.append("shares themes: " + ", ".join(shared[:3]))
            reason = "; ".join(why)
            # upper-case only the first letter; str.capitalize() would lowercase author names (LMS-BUG-009)
            scored.append((score, b, reason[:1].upper() + reason[1:]))
    similar = take((b, r) for _, b, r in sorted(scored, key=lambda x: (-x[0], rank(x[1]))))

    same_topic = take(
        (b, f"More from {b.category.name}, a topic you read")
        for b in sorted(unread, key=rank) if b.category_id in read_cats
    )

    # co-borrow: other readers of my books -> what else they read
    others = select(Loan.user_id).where(
        Loan.book_id.in_(read_ids), Loan.user_id != user_id, Loan.status.in_(COUNTED)
    )
    co = Counter(db.scalars(
        select(Loan.book_id).where(Loan.user_id.in_(others), Loan.status.in_(COUNTED))
    ).all())
    also = take(
        (by_id[bid], f"{n} reader(s) with your taste also borrowed this")
        for bid, n in co.most_common() if bid not in read_ids
    )

    seen_cats, different_candidates = set(), []
    for b in sorted(unread, key=rank):
        if b.category_id not in read_cats and b.category_id not in seen_cats:
            seen_cats.add(b.category_id)
            different_candidates.append((b, f"Try something new: top pick in {b.category.name}"))
    different = take(different_candidates)

    return {"close_in_meaning": close, "same_topic": same_topic, "similar": similar, "also_borrowed": also,
            "different": different, "popular": []}
