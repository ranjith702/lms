"""ORM object -> response schema helpers (adds derived fields like days_overdue)."""
from datetime import datetime, timezone

from app import schemas
from app.models import Book, Fine, Loan


def book_out(b: Book) -> schemas.BookOut:
    out = schemas.BookOut.model_validate(b)
    out.category_name = b.category.name if b.category else None
    return out


def loan_out(l: Loan, now: datetime | None = None) -> schemas.LoanOut:
    now = now or datetime.now(timezone.utc)
    overdue = (now.date() - l.due_at.date()).days if l.status == "borrowed" and l.due_at and l.due_at < now else 0
    return schemas.LoanOut(
        id=l.id, user_id=l.user_id, student_name=l.user.name if l.user else None, book=book_out(l.book),
        status=l.status, requested_at=l.requested_at, borrowed_at=l.borrowed_at, due_at=l.due_at,
        returned_at=l.returned_at, days_overdue=max(overdue, 0),
    )


def fine_out(f: Fine, student_name: str | None = None) -> schemas.FineOut:
    out = schemas.FineOut.model_validate(f)
    out.book_title = f.loan.book.title if f.loan and f.loan.book else None
    out.student_name = student_name
    return out


def trust_out(t) -> schemas.TrustOut:
    return schemas.TrustOut(**{k: getattr(t, k) for k in schemas.TrustOut.model_fields})


def rec_items(items: list[dict]) -> list[schemas.RecItem]:
    return [schemas.RecItem(book=book_out(i["book"]), reason=i["reason"]) for i in items]
