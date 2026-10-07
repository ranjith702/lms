"""Shared pytest fixtures. Tests run against the separate lms_test database."""
import os

# Tests never call real AI APIs (cost, flakiness): env vars beat .env, and this runs before app import.
os.environ["LMS_AI_PROVIDER"] = "none"

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.config import get_settings
from app.core.security import hash_password
from app.db import Base, get_db

TEST_URL = get_settings().test_database_url
assert TEST_URL and "lms_test" in TEST_URL, "LMS_TEST_DATABASE_URL must point at lms_test"

engine = create_engine(TEST_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def client():
    from app.main import app

    def override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


# ---------- factories ----------
def make_user(db, email="stu@test.dev", role="student", name="Stu", password="secret123"):
    u = models.User(name=name, email=email, role=role, password_hash=hash_password(password))
    db.add(u)
    db.commit()
    return u


def make_category(db, name="Fiction"):
    c = models.Category(name=name, description="")
    db.add(c)
    db.commit()
    return c


def make_book(db, category, title="Book", copies=1, tags=None, author="Author"):
    b = models.Book(
        title=title, author=author, category_id=category.id, description=f"About {title}",
        tags=tags or [], total_copies=copies, available_copies=copies,
    )
    db.add(b)
    db.commit()
    return b


def make_past_loan(db, user, book, days_late=0, returned=True, now=NOW):
    """A finished (or still-out) loan whose due date is in the past."""
    borrowed = now - timedelta(days=40)
    due = borrowed + timedelta(days=14)
    loan = models.Loan(
        user_id=user.id, book_id=book.id, status="returned" if returned else "borrowed",
        requested_at=borrowed, borrowed_at=borrowed, due_at=due,
        returned_at=(due + timedelta(days=days_late)) if returned else None,
    )
    db.add(loan)
    db.commit()
    return loan
