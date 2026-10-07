"""Librarian-side "assistant": explains a student's record and suggests what to do next.

Rule-based today. The returned `suggestions` are plain sentences, so an LLM can later
rewrite them more naturally without changing the API shape.
"""
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Book, Fine, Loan, User
from app.services import recommend_service, trust_service


def for_student(db: Session, student_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    student = db.get(User, student_id)
    loans = db.scalars(
        select(Loan).where(Loan.user_id == student_id)
        .options(joinedload(Loan.book).joinedload(Book.category))
        .order_by(Loan.requested_at.desc())
    ).unique().all()
    trust = trust_service.compute(db, student_id, now=now)

    cats = Counter(l.book.category.name for l in loans if l.status in ("borrowed", "returned"))
    overdue = [
        {"loan_id": l.id, "title": l.book.title, "days_overdue": (now.date() - l.due_at.date()).days}
        for l in loans if l.status == "borrowed" and l.due_at < now
    ]
    returned = trust.late_returns + trust.on_time_returns
    on_time_rate = round(100 * trust.on_time_returns / returned) if returned else None
    fines = db.scalars(select(Fine).where(Fine.user_id == student_id)).all()

    suggestions = []
    if overdue:
        suggestions.append(f"{len(overdue)} book(s) overdue - send a return reminder.")
    if trust.unpaid_fines:
        suggestions.append(f"Collect Rs {trust.unpaid_amount} in unpaid fines to restore borrowing.")
    if trust.level == "instant" and returned >= 3:
        suggestions.append("Reliable reader - safe to approve extra requests or reservations.")
    if trust.level == "approval":
        suggestions.append("Review this student's requests manually until the trust score is back above 70.")
    if trust.level == "blocked":
        suggestions.append("Borrowing is blocked; talk to the student about overdue books and fines.")
    if cats:
        top = cats.most_common(1)[0][0]
        suggestions.append(f"Mostly reads {top} - point them to new {top} arrivals.")
    if not loans:
        suggestions.append("Hasn't borrowed yet - recommend a popular starter book.")

    recs = recommend_service.for_student(db, student_id)
    suggest_next = [r for key in ("similar", "same_topic", "also_borrowed", "popular", "different")
                    for r in recs[key]][:5]

    return {
        "student": student,
        "trust": trust,
        "loans": loans,
        "overdue": overdue,
        "fines": fines,
        "favorite_categories": [{"name": n, "count": c} for n, c in cats.most_common(3)],
        "on_time_rate": on_time_rate,
        "suggestions": suggestions,
        "suggest_next": suggest_next,
    }


def at_risk_students(db: Session, now: datetime | None = None) -> list[dict]:
    students = db.scalars(select(User).where(User.role == "student").order_by(User.name)).all()
    out = []
    for s in students:
        t = trust_service.compute(db, s.id, now=now)
        if t.level != "instant":
            out.append({"id": s.id, "name": s.name, "email": s.email, "score": t.score,
                        "level": t.level, "reasons": t.reasons})
    return sorted(out, key=lambda x: x["score"])
