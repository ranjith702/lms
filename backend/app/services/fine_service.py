from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fine, User
from app.services import activity
from app.services.errors import ServiceError


def mark(db: Session, librarian: User, fine_id: int, new_status: str, now: datetime | None = None) -> Fine:
    if new_status not in ("paid", "waived"):
        raise ServiceError(400, "Status must be paid or waived")
    fine = db.scalar(select(Fine).where(Fine.id == fine_id).with_for_update())
    if fine is None:
        raise ServiceError(404, "Fine not found")
    if fine.status != "unpaid":
        raise ServiceError(409, f"Fine is already {fine.status}")
    fine.status, fine.paid_at = new_status, now or datetime.now(timezone.utc)
    activity.log(db, librarian.id, f"fine.{new_status}", "fine", fine.id, amount=fine.amount, student_id=fine.user_id)
    db.commit()
    return fine
