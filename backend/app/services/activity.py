from sqlalchemy.orm import Session

from app.models import Activity


def log(db: Session, user_id: int | None, action: str, entity: str, entity_id: int | None, **details) -> None:
    """Add an audit row to the current transaction (committed together with the change)."""
    db.add(Activity(user_id=user_id, action=action, entity=entity, entity_id=entity_id, details=details))
