import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import get_settings
from app.core.security import (COOKIE_NAME, create_token, get_current_session, get_current_user, hash_password,
                               verify_password)
from app.db import get_db
from app.models import User, UserSession
from app.routers._convert import trust_out
from app.services import activity, trust_service
from app.services.rate_limit import LoginLimiter

router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = LoginLimiter(window_seconds=get_settings().login_window_seconds)


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


def _set_auth_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME, token, max_age=s.jwt_expire_minutes * 60, path="/api",
        httponly=True,       # page JavaScript can't read it
        secure=s.cookie_secure,
        samesite="lax",      # not sent on cross-site POSTs, which blocks CSRF from other sites
    )


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    account_key, ip_key = f"{ip}|{email}", f"ip:{ip}"
    wait = max(login_limiter.retry_after(account_key, s.login_max_failures),
               login_limiter.retry_after(ip_key, s.login_max_failures_per_ip))
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed logins. Try again in {math.ceil(wait / 60)} minute(s).",
                            headers={"Retry-After": str(wait)})

    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        login_limiter.record_failure(account_key, ip_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    login_limiter.reset(account_key)  # the IP counter keeps counting, so stuffing can't hide behind one good account
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
    token = create_token(user, session.id)
    _set_auth_cookie(response, token)
    # The token is also in the body for API clients (Postman, scripts); the browser app ignores it.
    return schemas.TokenOut(access_token=token, user=user, previous_session=previous)


@router.post("/logout", status_code=204)
def logout(response: Response, session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    session = db.merge(session)
    session.logout_at = datetime.now(timezone.utc)
    activity.log(db, session.user_id, "auth.logout", "user", session.user_id)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api", httponly=True, secure=get_settings().cookie_secure, samesite="lax")


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
