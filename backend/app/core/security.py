"""Password hashing + JWT + "who is calling?" dependencies.

Flow: login -> create a sessions row -> JWT carries that session id (sid).
Every request: decode JWT -> look up the session -> reject if logged out.
That is what makes logout real, even though JWTs are normally stateless.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, UserSession

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: User, session_id: uuid.UUID) -> str:
    s = get_settings()
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "sid": str(session_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_session(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserSession:
    if creds is None:
        raise _unauthorized()
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=[ALGORITHM])
        sid = uuid.UUID(payload["sid"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired token")
    session = db.get(UserSession, sid)
    if session is None or session.logout_at is not None:
        raise _unauthorized("Session has ended, please log in again")
    return session


def get_current_user(
    session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)
) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise _unauthorized()
    return user


def require_librarian(user: User = Depends(get_current_user)) -> User:
    if user.role != "librarian":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Librarian access required")
    return user
