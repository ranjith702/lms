"""Trust score: computed from history every time, never stored, so it can't go stale.

score = 100 - 10*late_returns - 15*unpaid_fines - 25*(any overdue now) + 2*on_time_returns
clamped to 0..100.  >=70 instant borrow, 40-69 librarian approval, <40 blocked.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Fine, Loan

INSTANT_MIN = 70
APPROVAL_MIN = 40


@dataclass
class TrustReport:
    score: int
    level: str  # instant | approval | blocked
    reasons: list[str] = field(default_factory=list)
    late_returns: int = 0
    on_time_returns: int = 0
    unpaid_fines: int = 0
    unpaid_amount: int = 0
    overdue_now: int = 0


def level_for(score: int) -> str:
    if score >= INSTANT_MIN:
        return "instant"
    if score >= APPROVAL_MIN:
        return "approval"
    return "blocked"


def compute(db: Session, user_id: int, now: datetime | None = None) -> TrustReport:
    now = now or datetime.now(timezone.utc)
    returned = db.execute(
        select(Loan.due_at, Loan.returned_at).where(Loan.user_id == user_id, Loan.status == "returned")
    ).all()
    late = sum(1 for due, ret in returned if due and ret and ret.date() > due.date())
    on_time = len(returned) - late
    overdue = db.scalar(
        select(func.count()).select_from(Loan)
        .where(Loan.user_id == user_id, Loan.status == "borrowed", Loan.due_at < now)
    ) or 0
    unpaid_count, unpaid_amount = db.execute(
        select(func.count(), func.coalesce(func.sum(Fine.amount), 0))
        .where(Fine.user_id == user_id, Fine.status == "unpaid")
    ).one()

    score = 100 - 10 * late - 15 * unpaid_count - (25 if overdue else 0) + 2 * on_time
    score = max(0, min(100, score))

    reasons = []
    if late:
        reasons.append(f"{late} late return(s) (-{10 * late})")
    if unpaid_count:
        reasons.append(f"{unpaid_count} unpaid fine(s), Rs {unpaid_amount} (-{15 * unpaid_count})")
    if overdue:
        reasons.append(f"{overdue} book(s) overdue right now (-25)")
    if on_time:
        reasons.append(f"{on_time} on-time return(s) (+{2 * on_time})")
    if not reasons:
        reasons.append("New reader with a clean record")

    return TrustReport(score, level_for(score), reasons, late, on_time, unpaid_count, unpaid_amount, overdue)
