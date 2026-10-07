from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.core.security import create_token, get_current_session, get_current_user, hash_password, verify_password
from app.db import get_db
from app.models import User, UserSession
from app.routers._convert import trust_out
from app.services import activity, trust_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    # Self-registration is always a student; librarians are created by seed/admin only.
    user = User(name=body.name.strip(), email=email, role="student", password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    activity.log(db, user.id, "user.registered", "user", user.id)
    db.commit()
    return user


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    previous = db.scalar(
        select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.login_at.desc()).limit(1)
    )
    session = UserSession(
        user_id=user.id,
        ip=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(session)
    db.flush()
    activity.log(db, user.id, "auth.login", "user", user.id)
    db.commit()
    return schemas.TokenOut(access_token=create_token(user, session.id), user=user, previous_session=previous)


@router.post("/logout", status_code=204)
def logout(session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    session = db.merge(session)
    session.logout_at = datetime.now(timezone.utc)
    activity.log(db, session.user_id, "auth.logout", "user", session.user_id)
    db.commit()


@router.get("/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/sessions", response_model=list[schemas.SessionOut])
def my_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.login_at.desc()).limit(50)
    ).all()


@router.get("/me/trust", response_model=schemas.TrustOut)
def my_trust(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return trust_out(trust_service.compute(db, user.id))
