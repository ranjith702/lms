"""Loans + fines endpoints. Rules live in services; this file only does HTTP."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app.core.security import get_current_user, require_librarian
from app.db import get_db
from app.models import Book, Fine, Loan, User
from app.routers._convert import fine_out, loan_out
from app.services import fine_service, loan_service, trust_service

router = APIRouter(tags=["loans & fines"])

LOAN_OPTS = (joinedload(Loan.book).joinedload(Book.category), joinedload(Loan.user))


def _load(db: Session, loan_id: int) -> Loan:
    return db.scalar(select(Loan).options(*LOAN_OPTS).where(Loan.id == loan_id).execution_options(populate_existing=True))


@router.post("/loans", response_model=schemas.BorrowOut, status_code=201)
def borrow(body: schemas.BorrowIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loan = loan_service.borrow(db, user, body.book_id)
    trust = trust_service.compute(db, user.id)
    loan = _load(db, loan.id)
    if loan.status == "borrowed":
        msg = f"Borrowed! Due back on {loan.due_at:%d %b %Y}."
    else:
        msg = f"Request sent to the librarian for approval (trust score {trust.score})."
    return schemas.BorrowOut(loan=loan_out(loan), message=msg, trust_score=trust.score)


@router.post("/loans/{loan_id}/return", response_model=schemas.LoanOut)
def return_book(loan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loan_service.return_loan(db, user, loan_id)
    return loan_out(_load(db, loan_id))


@router.get("/loans/me", response_model=list[schemas.LoanOut])
def my_loans(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loans = db.scalars(select(Loan).options(*LOAN_OPTS).where(Loan.user_id == user.id)
                       .order_by(Loan.requested_at.desc())).all()
    return [loan_out(l) for l in loans]


@router.get("/loans", response_model=list[schemas.LoanOut])
def all_loans(
    status: str | None = Query(None, pattern="^(pending|borrowed|returned|rejected|overdue)$"),
    db: Session = Depends(get_db), _: User = Depends(require_librarian),
):
    stmt = select(Loan).options(*LOAN_OPTS).order_by(Loan.requested_at.desc()).limit(500)
    if status == "overdue":
        stmt = stmt.where(Loan.status == "borrowed", Loan.due_at < datetime.now(timezone.utc))
    elif status:
        stmt = stmt.where(Loan.status == status)
    return [loan_out(l) for l in db.scalars(stmt)]


@router.post("/loans/{loan_id}/approve", response_model=schemas.LoanOut)
def approve(loan_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    loan_service.approve(db, lib, loan_id)
    return loan_out(_load(db, loan_id))


@router.post("/loans/{loan_id}/reject", response_model=schemas.LoanOut)
def reject(loan_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    loan_service.reject(db, lib, loan_id)
    return loan_out(_load(db, loan_id))


FINE_OPTS = (joinedload(Fine.loan).joinedload(Loan.book), joinedload(Fine.loan).joinedload(Loan.user))


@router.get("/fines/me", response_model=list[schemas.FineOut])
def my_fines(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fines = db.scalars(select(Fine).options(*FINE_OPTS).where(Fine.user_id == user.id).order_by(Fine.created_at.desc())).all()
    return [fine_out(f, user.name) for f in fines]


@router.get("/fines", response_model=list[schemas.FineOut])
def all_fines(
    status: str | None = Query(None, pattern="^(unpaid|paid|waived)$"),
    db: Session = Depends(get_db), _: User = Depends(require_librarian),
):
    stmt = select(Fine).options(*FINE_OPTS).order_by(Fine.created_at.desc())
    if status:
        stmt = stmt.where(Fine.status == status)
    return [fine_out(f, f.loan.user.name) for f in db.scalars(stmt)]


@router.post("/fines/{fine_id}/pay", response_model=schemas.FineOut)
def pay(fine_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    fine = fine_service.mark(db, lib, fine_id, "paid")
    return fine_out(fine)


@router.post("/fines/{fine_id}/waive", response_model=schemas.FineOut)
def waive(fine_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    fine = fine_service.mark(db, lib, fine_id, "waived")
    return fine_out(fine)
