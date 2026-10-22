import hashlib
import jwt
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_security import BrowserSession, PasswordResetToken
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    *,
    session_id: str,
) -> str:
    if not session_id:
        raise ValueError("A session ID is required to create an access token.")
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "exp": datetime.utcnow() + expires_delta}
    to_encode["sid"] = session_id
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email.lower()).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_token_payload(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def issue_password_reset(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.consumed_at.is_(None),
    ).update({PasswordResetToken.consumed_at: now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        user_id=user.id,
        expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
    ))
    db.commit()
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> bool:
    now = datetime.now(timezone.utc)
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        PasswordResetToken.consumed_at.is_(None),
    ).with_for_update().first()
    if not reset:
        return False
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return False

    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user or not user.active:
        return False
    reset.consumed_at = now
    user.password_hash = get_password_hash(new_password)
    db.query(BrowserSession).filter(
        BrowserSession.user_id == user.id,
        BrowserSession.revoked_at.is_(None),
    ).update({BrowserSession.revoked_at: now}, synchronize_session=False)
    db.commit()
    return True
