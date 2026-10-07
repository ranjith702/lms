"""Borrow / approve / reject / return. All the loan rules live here."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Book, Fine, Loan, User
from app.services import activity, trust_service
from app.services.errors import ServiceError

ACTIVE = ("pending", "borrowed")


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _take_copy(db: Session, book_id: int) -> None:
    """Atomic decrement: only succeeds if a copy is left, even with concurrent requests."""
    result = db.execute(
        update(Book)
        .where(Book.id == book_id, Book.available_copies > 0)
        .values(available_copies=Book.available_copies - 1)
    )
    if result.rowcount == 0:
        db.rollback()
        raise ServiceError(409, "No copies available right now")


def _put_back_copy(db: Session, book_id: int) -> None:
    db.execute(update(Book).where(Book.id == book_id).values(available_copies=Book.available_copies + 1))


def borrow(db: Session, user: User, book_id: int, now: datetime | None = None) -> Loan:
    now, s = _now(now), get_settings()
    if user.role != "student":
        raise ServiceError(403, "Only students can borrow books")
    if db.get(Book, book_id) is None:
        raise ServiceError(404, "Book not found")

    # Lock this student's row until commit: parallel borrow requests from the SAME student
    # queue up here, so the limit/duplicate checks below can't be raced (LMS-BUG-006).
    db.execute(select(User.id).where(User.id == user.id).with_for_update())

    active = db.scalars(select(Loan).where(Loan.user_id == user.id, Loan.status.in_(ACTIVE))).all()
    if any(l.book_id == book_id for l in active):
        raise ServiceError(409, "You already have this book (or a pending request for it)")
    if len(active) >= s.max_active_loans:
        raise ServiceError(409, f"Loan limit reached ({s.max_active_loans} active books). Return one first.")

    trust = trust_service.compute(db, user.id, now=now)
    if trust.level == "blocked":
        raise ServiceError(403, f"Borrowing blocked (trust score {trust.score}). Pay fines / return overdue books first.")

    _take_copy(db, book_id)
    if trust.level == "instant":
        loan = Loan(user_id=user.id, book_id=book_id, status="borrowed",
                    requested_at=now, borrowed_at=now, due_at=now + timedelta(days=s.loan_days))
    else:
        loan = Loan(user_id=user.id, book_id=book_id, status="pending", requested_at=now)
    db.add(loan)
    db.flush()
    activity.log(db, user.id, f"loan.{loan.status}", "loan", loan.id, book_id=book_id, trust=trust.score)
    db.commit()
    return loan


def _get_loan(db: Session, loan_id: int, lock: bool = True) -> Loan:
    stmt = select(Loan).where(Loan.id == loan_id)
    if lock:
        stmt = stmt.with_for_update()  # stops two librarians approving the same request at once
    loan = db.scalar(stmt)
    if loan is None:
        raise ServiceError(404, "Loan not found")
    return loan


def approve(db: Session, librarian: User, loan_id: int, now: datetime | None = None) -> Loan:
    now = _now(now)
    loan = _get_loan(db, loan_id)
    if loan.status != "pending":
        raise ServiceError(409, f"Loan is {loan.status}, not pending")
    loan.status, loan.borrowed_at, loan.decided_by = "borrowed", now, librarian.id
    loan.due_at = now + timedelta(days=get_settings().loan_days)
    activity.log(db, librarian.id, "loan.approved", "loan", loan.id, student_id=loan.user_id)
    db.commit()
    return loan


def reject(db: Session, librarian: User, loan_id: int) -> Loan:
    loan = _get_loan(db, loan_id)
    if loan.status != "pending":
        raise ServiceError(409, f"Loan is {loan.status}, not pending")
    loan.status, loan.decided_by = "rejected", librarian.id
    _put_back_copy(db, loan.book_id)
    activity.log(db, librarian.id, "loan.rejected", "loan", loan.id, student_id=loan.user_id)
    db.commit()
    return loan


def return_loan(db: Session, actor: User, loan_id: int, now: datetime | None = None) -> Loan:
    now = _now(now)
    loan = _get_loan(db, loan_id)
    if actor.role != "librarian" and loan.user_id != actor.id:
        raise ServiceError(403, "You can only return your own books")
    if loan.status != "borrowed":
        raise ServiceError(409, f"Loan is {loan.status}, not borrowed")
    loan.status, loan.returned_at = "returned", now
    _put_back_copy(db, loan.book_id)

    days_late = (now.date() - loan.due_at.date()).days
    if days_late > 0:
        amount = days_late * get_settings().fine_per_day
        db.add(Fine(loan_id=loan.id, user_id=loan.user_id, days_late=days_late, amount=amount))
    activity.log(db, actor.id, "loan.returned", "loan", loan.id, days_late=max(days_late, 0))
    db.commit()
    return loan


def active_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Loan).where(Loan.status == "borrowed")) or 0
