import hmac
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.auth_security import BrowserSession
from app.models.user import User
from app.services.auth_service import get_token_payload, get_user_by_email

security = HTTPBearer(auto_error=False)


def validate_cookie_csrf(request: Request) -> None:
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name, "")
    csrf_header = request.headers.get("X-CSRF-Token", "")
    validate_request_origin(request)
    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")


def validate_request_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    configured_origins = {
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    }
    if settings.frontend_url:
        configured_origins.add(settings.frontend_url)
    if origin not in configured_origins:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


async def get_current_active_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    cookie_auth = credentials is None
    token = credentials.credentials if credentials else None
    if cookie_auth and settings.auth_cookie_enabled:
        token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    payload = get_token_payload(token)
    email = payload.get("sub")
    session_id = payload.get("sid")
    if not email or not isinstance(session_id, str) or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    session = db.query(BrowserSession).filter(BrowserSession.id == session_id).first()
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    if cookie_auth and settings.auth_cookie_enabled:
        if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            validate_cookie_csrf(request)

    user = get_user_by_email(db, email)
    if user is None or not user.active or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return user


def require_role(allowed_roles):
    def role_checker(user: User = Depends(get_current_active_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to perform this action.")
        return user

    return role_checker
