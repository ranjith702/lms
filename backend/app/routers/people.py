"""Librarian views of students, dashboard, activity; student recommendations + assistant."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.core.security import get_current_user, require_librarian
from app.db import get_db
from app.models import Activity, Book, Fine, Loan, User, UserSession
from app.routers._convert import book_out, fine_out, loan_out, rec_items, trust_out
from app.ai.provider import AIError, get_provider
from app.services import activity, assistant_service, insights_service, recommend_service, trust_service

router = APIRouter(tags=["people & insights"])


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_librarian)):
    now = datetime.now(timezone.utc)
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    return schemas.DashboardOut(
        books=count(select(func.count()).select_from(Book)),
        copies_out=count(select(func.count()).select_from(Loan).where(Loan.status == "borrowed")),
        pending=count(select(func.count()).select_from(Loan).where(Loan.status == "pending")),
        overdue=count(select(func.count()).select_from(Loan).where(Loan.status == "borrowed", Loan.due_at < now)),
        unpaid_fines_total=count(select(func.coalesce(func.sum(Fine.amount), 0)).where(Fine.status == "unpaid")),
        students=count(select(func.count()).select_from(User).where(User.role == "student")),
        at_risk=insights_service.at_risk_students(db, now=now),
    )


@router.get("/users/students", response_model=list[schemas.StudentRow])
def students(db: Session = Depends(get_db), _: User = Depends(require_librarian)):
    active = dict(db.execute(
        select(Loan.user_id, func.count()).where(Loan.status.in_(("pending", "borrowed"))).group_by(Loan.user_id)
    ).all())
    rows = []
    for s in db.scalars(select(User).where(User.role == "student").order_by(User.name)):
        t = trust_service.compute(db, s.id)
        rows.append(schemas.StudentRow(id=s.id, name=s.name, email=s.email, score=t.score, level=t.level,
                                       active_loans=active.get(s.id, 0), unpaid_amount=t.unpaid_amount))
    return rows


@router.get("/users/{user_id}/insights", response_model=schemas.InsightsOut)
def insights(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_librarian)):
    student = db.get(User, user_id)
    if student is None or student.role != "student":
        raise HTTPException(404, "Student not found")
    d = insights_service.for_student(db, user_id)
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user_id)
                          .order_by(UserSession.login_at.desc()).limit(10)).all()
    return schemas.InsightsOut(
        student=schemas.UserOut.model_validate(student), trust=trust_out(d["trust"]),
        loans=[loan_out(l) for l in d["loans"]], overdue=d["overdue"],
        fines=[fine_out(f, student.name) for f in d["fines"]],
        favorite_categories=d["favorite_categories"], on_time_rate=d["on_time_rate"],
        suggestions=d["suggestions"], suggest_next=rec_items(d["suggest_next"]),
        sessions=[schemas.SessionOut.model_validate(s) for s in sessions],
    )


@router.get("/recommendations/me", response_model=schemas.RecommendationsOut)
def my_recommendations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    recs = recommend_service.for_student(db, user.id)
    return schemas.RecommendationsOut(**{k: rec_items(v) for k, v in recs.items()})


@router.post("/assistant/ask", response_model=schemas.AskOut)
def ask(body: schemas.AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = assistant_service.ask(db, user, body.question)
    return schemas.AskOut(answer=r["answer"], books=[book_out(b) for b in r["books"]], provider=r["provider"],
                          retrieval=r["retrieval"], found_by={str(k): v for k, v in r["found_by"].items()},
                          recommended=r["recommended"], error=r["error"])


@router.post("/users/{user_id}/ai-brief", response_model=schemas.BriefOut)
def ai_brief(user_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    student = db.get(User, user_id)
    if student is None or student.role != "student":
        raise HTTPException(404, "Student not found")
    try:
        brief, model = insights_service.ai_brief(db, user_id, get_provider())
    except AIError as e:
        raise HTTPException(503, f"AI brief unavailable: {e}")
    activity.log(db, lib.id, "assistant.brief", "user", user_id, model=model)
    db.commit()
    return schemas.BriefOut(brief=brief, model=model)


def _activity(db: Session, stmt) -> list[schemas.ActivityOut]:
    rows = db.execute(stmt.outerjoin(User, User.id == Activity.user_id).add_columns(User.name)).all()
    out = []
    for a, name in rows:
        item = schemas.ActivityOut.model_validate(a)
        item.user_name = name
        out.append(item)
    return out


@router.get("/activity", response_model=list[schemas.ActivityOut])
def activity_feed(
    user_id: int | None = None, limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db), _: User = Depends(require_librarian),
):
    stmt = select(Activity).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit)
    if user_id:
        stmt = stmt.where(Activity.user_id == user_id)
    return _activity(db, stmt)


@router.get("/activity/me", response_model=list[schemas.ActivityOut])
def my_activity(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Activity).where(Activity.user_id == user.id).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(100)
    return _activity(db, stmt)
