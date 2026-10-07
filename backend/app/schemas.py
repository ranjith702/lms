"""Pydantic schemas = the exact JSON shapes the API accepts and returns.

Response models never include password_hash: what the API can leak is decided here.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime


class SessionOut(ORM):
    id: UUID
    login_at: datetime
    logout_at: datetime | None
    ip: str | None
    user_agent: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    previous_session: SessionOut | None  # "last login / last logout" shown after login


# ---------- catalog ----------
class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = ""


class CategoryOut(ORM):
    id: int
    name: str
    description: str
    book_count: int = 0


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    isbn: str | None = Field(default=None, max_length=20)
    category_id: int
    description: str = ""
    tags: list[str] = []
    total_copies: int = Field(default=1, ge=1, le=100)
    cover_color: str = Field(default="#334155", pattern=r"^#[0-9a-fA-F]{6}$")


class BookOut(ORM):
    id: int
    title: str
    author: str
    isbn: str | None
    category_id: int
    category_name: str | None = None
    description: str
    tags: list[str]
    total_copies: int
    available_copies: int
    cover_color: str


# ---------- loans / fines ----------
class BorrowIn(BaseModel):
    book_id: int


class LoanOut(ORM):
    id: int
    user_id: int
    student_name: str | None = None
    book: BookOut
    status: str
    requested_at: datetime
    borrowed_at: datetime | None
    due_at: datetime | None
    returned_at: datetime | None
    days_overdue: int = 0


class BorrowOut(BaseModel):
    loan: LoanOut
    message: str
    trust_score: int


class FineOut(ORM):
    id: int
    loan_id: int
    user_id: int
    student_name: str | None = None
    book_title: str | None = None
    days_late: int
    amount: int
    status: str
    created_at: datetime
    paid_at: datetime | None


# ---------- trust / insights / recommendations ----------
class TrustOut(BaseModel):
    score: int
    level: str
    reasons: list[str]
    late_returns: int
    on_time_returns: int
    unpaid_fines: int
    unpaid_amount: int
    overdue_now: int


class RecItem(BaseModel):
    book: BookOut
    reason: str


class RecommendationsOut(BaseModel):
    same_topic: list[RecItem]
    similar: list[RecItem]
    also_borrowed: list[RecItem]
    different: list[RecItem]
    popular: list[RecItem]


class StudentRow(BaseModel):
    id: int
    name: str
    email: str
    score: int
    level: str
    active_loans: int
    unpaid_amount: int


class InsightsOut(BaseModel):
    student: UserOut
    trust: TrustOut
    loans: list[LoanOut]
    overdue: list[dict]
    fines: list[FineOut]
    favorite_categories: list[dict]
    on_time_rate: int | None
    suggestions: list[str]
    suggest_next: list[RecItem]
    sessions: list[SessionOut]


class DashboardOut(BaseModel):
    books: int
    copies_out: int
    pending: int
    overdue: int
    unpaid_fines_total: int
    students: int
    at_risk: list[dict]


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class AskOut(BaseModel):
    answer: str
    books: list[BookOut]
    provider: str


class ActivityOut(ORM):
    id: int
    user_id: int | None
    user_name: str | None = None
    action: str
    entity: str
    entity_id: int | None
    details: dict
    created_at: datetime
