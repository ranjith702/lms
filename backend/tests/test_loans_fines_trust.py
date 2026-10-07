"""Business rules: trust score, borrow/approve/return, fines. Written before the services."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app import models
from app.services import fine_service, loan_service, trust_service
from app.services.errors import ServiceError
from tests.conftest import NOW, TestingSession, make_book, make_category, make_past_loan, make_user


# ---------------- trust score ----------------
def test_new_student_has_full_trust_and_instant_level(db):
    stu = make_user(db)
    report = trust_service.compute(db, stu.id, now=NOW)
    assert report.score == 100
    assert report.level == "instant"


def test_late_returns_and_unpaid_fines_lower_trust(db):
    stu, cat = make_user(db), make_category(db)
    for i in range(2):
        loan = make_past_loan(db, stu, make_book(db, cat, f"B{i}"), days_late=3)
        db.add(models.Fine(loan_id=loan.id, user_id=stu.id, days_late=3, amount=15, status="unpaid"))
    db.commit()
    report = trust_service.compute(db, stu.id, now=NOW)
    # 100 - 2*10 (late) - 2*15 (unpaid) = 50
    assert report.score == 50
    assert report.level == "approval"
    assert any("late" in r for r in report.reasons)


def test_currently_overdue_drops_to_blocked(db):
    stu, cat = make_user(db), make_category(db)
    make_past_loan(db, stu, make_book(db, cat, "Out"), returned=False)  # overdue now
    late = [make_past_loan(db, stu, make_book(db, cat, f"L{i}"), days_late=5) for i in range(3)]
    report = trust_service.compute(db, stu.id, now=NOW)
    # 100 - 25 (overdue) - 30 (3 late) = 45 -> approval; one unpaid fine (-15) pushes to blocked
    assert report.score == 45
    db.add(models.Fine(loan_id=late[0].id, user_id=stu.id, days_late=5, amount=25))
    db.commit()
    assert trust_service.compute(db, stu.id, now=NOW).level == "blocked"


def test_on_time_returns_recover_trust(db):
    stu, cat = make_user(db), make_category(db)
    make_past_loan(db, stu, make_book(db, cat, "Late"), days_late=2)
    for i in range(5):
        make_past_loan(db, stu, make_book(db, cat, f"Ok{i}"), days_late=0)
    # 100 - 10 + 5*2 = 100 (capped)
    assert trust_service.compute(db, stu.id, now=NOW).score == 100


# ---------------- borrowing ----------------
def test_trusted_student_borrows_instantly(db):
    stu, cat = make_user(db), make_category(db)
    book = make_book(db, cat, copies=2)
    loan = loan_service.borrow(db, stu, book.id, now=NOW)
    assert loan.status == "borrowed"
    assert loan.due_at == NOW + timedelta(days=14)
    db.refresh(book)
    assert book.available_copies == 1


def test_low_trust_student_goes_to_pending_and_copy_is_reserved(db):
    stu, cat = make_user(db), make_category(db)
    for i in range(2):
        loan = make_past_loan(db, stu, make_book(db, cat, f"B{i}"), days_late=3)
        db.add(models.Fine(loan_id=loan.id, user_id=stu.id, days_late=3, amount=15))
    db.commit()
    book = make_book(db, cat, "Wanted")
    loan = loan_service.borrow(db, stu, book.id, now=NOW)
    assert loan.status == "pending"
    db.refresh(book)
    assert book.available_copies == 0


def test_blocked_student_cannot_borrow(db):
    stu, cat = make_user(db), make_category(db)
    make_past_loan(db, stu, make_book(db, cat, "Out"), returned=False)
    for i in range(4):
        make_past_loan(db, stu, make_book(db, cat, f"L{i}"), days_late=5)
    with pytest.raises(ServiceError) as e:
        loan_service.borrow(db, stu, make_book(db, cat, "New").id, now=NOW)
    assert e.value.status_code == 403


def test_cannot_borrow_when_no_copies(db):
    a, b, cat = make_user(db), make_user(db, "b@test.dev"), make_category(db)
    book = make_book(db, cat, copies=1)
    loan_service.borrow(db, a, book.id, now=NOW)
    with pytest.raises(ServiceError) as e:
        loan_service.borrow(db, b, book.id, now=NOW)
    assert e.value.status_code == 409


def test_cannot_borrow_same_book_twice_or_exceed_limit(db):
    stu, cat = make_user(db), make_category(db)
    book = make_book(db, cat, copies=5)
    loan_service.borrow(db, stu, book.id, now=NOW)
    with pytest.raises(ServiceError):
        loan_service.borrow(db, stu, book.id, now=NOW)
    for i in range(2):
        loan_service.borrow(db, stu, make_book(db, cat, f"X{i}").id, now=NOW)
    with pytest.raises(ServiceError) as e:
        loan_service.borrow(db, stu, make_book(db, cat, "Fourth").id, now=NOW)
    assert "limit" in e.value.message.lower()


def test_concurrent_borrow_of_last_copy_issues_it_once(db):
    cat = make_category(db)
    book = make_book(db, cat, copies=1)
    students = [make_user(db, f"s{i}@test.dev") for i in range(6)]

    def attempt(user_id):
        s = TestingSession()
        try:
            loan_service.borrow(s, s.get(models.User, user_id), book.id, now=NOW)
            return "ok"
        except ServiceError:
            return "fail"
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, [u.id for u in students]))
    assert results.count("ok") == 1
    db.refresh(book)
    assert book.available_copies == 0


# ---------------- approve / reject ----------------
def test_librarian_approves_and_rejects_pending(db):
    lib, cat = make_user(db, "lib@test.dev", role="librarian"), make_category(db)
    stu = make_user(db)
    book = make_book(db, cat, copies=2)
    p1 = models.Loan(user_id=stu.id, book_id=book.id, status="pending")
    p2 = models.Loan(user_id=stu.id, book_id=book.id, status="pending")
    book.available_copies = 0
    db.add_all([p1, p2])
    db.commit()
    approved = loan_service.approve(db, lib, p1.id, now=NOW)
    assert approved.status == "borrowed" and approved.due_at == NOW + timedelta(days=14)
    rejected = loan_service.reject(db, lib, p2.id)
    assert rejected.status == "rejected"
    db.refresh(book)
    assert book.available_copies == 1  # rejected copy goes back on the shelf


# ---------------- return + fines ----------------
@pytest.mark.parametrize("days_late,expected_fine", [(0, None), (1, 5), (10, 50)])
def test_return_creates_fine_only_when_late(db, days_late, expected_fine):
    stu, cat = make_user(db), make_category(db)
    book = make_book(db, cat)
    loan = loan_service.borrow(db, stu, book.id, now=NOW)
    returned_at = loan.due_at + timedelta(days=days_late)
    loan_service.return_loan(db, stu, loan.id, now=returned_at)
    fine = db.query(models.Fine).filter_by(loan_id=loan.id).one_or_none()
    if expected_fine is None:
        assert fine is None
    else:
        assert fine.amount == expected_fine and fine.days_late == days_late
    db.refresh(book)
    assert book.available_copies == 1


def test_student_cannot_return_someone_elses_loan(db):
    a, b, cat = make_user(db), make_user(db, "b@test.dev"), make_category(db)
    loan = loan_service.borrow(db, a, make_book(db, cat).id, now=NOW)
    with pytest.raises(ServiceError) as e:
        loan_service.return_loan(db, b, loan.id, now=NOW)
    assert e.value.status_code == 403


def test_pay_and_waive_fine(db):
    lib, stu, cat = make_user(db, "lib@test.dev", role="librarian"), make_user(db), make_category(db)
    loan = make_past_loan(db, stu, make_book(db, cat), days_late=2)
    fine = models.Fine(loan_id=loan.id, user_id=stu.id, days_late=2, amount=10)
    db.add(fine)
    db.commit()
    paid = fine_service.mark(db, lib, fine.id, "paid", now=NOW)
    assert paid.status == "paid" and paid.paid_at == NOW
    with pytest.raises(ServiceError):
        fine_service.mark(db, lib, fine.id, "waived", now=NOW)  # already settled


def test_every_action_is_logged(db):
    stu, cat = make_user(db), make_category(db)
    loan = loan_service.borrow(db, stu, make_book(db, cat).id, now=NOW)
    loan_service.return_loan(db, stu, loan.id, now=NOW)
    actions = [a.action for a in db.query(models.Activity).order_by(models.Activity.id)]
    assert actions == ["loan.borrowed", "loan.returned"]
