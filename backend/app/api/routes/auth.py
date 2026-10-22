import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, validate_cookie_csrf, validate_request_origin
from app.core.config import settings
from app.db.database import get_db
from app.models.auth_security import BrowserSession
from app.models.user import User
from app.schemas.auth import PasswordResetComplete, PasswordResetRequest, Token, UserLogin, UserRegister, UserResponse
from app.services.auth_service import authenticate_user, create_access_token, get_password_hash, get_token_payload, get_user_by_email, issue_password_reset, reset_password
from app.services.email_service import send_password_reset_email
from app.services.rate_limit_service import limit_login, limit_password_reset, limit_registration

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)
optional_bearer = HTTPBearer(auto_error=False)


def _deliver_password_reset_email(recipient: str, raw_token: str) -> None:
    try:
        send_password_reset_email(recipient, raw_token)
    except (smtplib.SMTPException, OSError, ssl.SSLError):
        logger.error("Password reset email delivery failed.")


def _set_auth_cookies(response: Response, access_token: str, csrf_token: str) -> None:
    max_age = settings.access_token_expire_minutes * 60
    cookie_options = {
        "max_age": max_age,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite.lower(),
        "path": "/",
    }
    response.set_cookie(
        settings.auth_cookie_name,
        access_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=True,
        **cookie_options,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    _: None = Depends(limit_registration),
    db: Session = Depends(get_db),
):
    if payload.role not in {"requester", "donor"}:
        raise HTTPException(status_code=403, detail="Public registration is limited to requester and donor roles.")
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        phone=payload.phone,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        college_org=payload.college_org,
        nss_unit=payload.nss_unit,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    x_auth_mode: str | None = Header(default=None),
    _: None = Depends(limit_login),
    db: Session = Depends(get_db),
):
    use_cookie_session = settings.auth_cookie_enabled and (x_auth_mode or "").lower() != "bearer"
    if use_cookie_session:
        validate_request_origin(request)
    user = authenticate_user(db, payload.email, payload.password)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + expires_delta
    db.add(BrowserSession(id=session_id, user_id=user.id, expires_at=expires_at))
    db.commit()
    token = create_access_token(str(user.email), expires_delta, session_id=session_id)
    csrf_token = None
    if use_cookie_session:
        csrf_token = secrets.token_urlsafe(32)
        _set_auth_cookies(response, token, csrf_token)
    return {
        "access_token": None if use_cookie_session else token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
    }


@router.get("/csrf")
async def get_csrf_token(request: Request, response: Response):
    if not settings.auth_cookie_enabled:
        return {"csrf_token": None}
    csrf_token = request.cookies.get(settings.csrf_cookie_name)
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            settings.csrf_cookie_name,
            csrf_token,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite.lower(),
            path="/",
        )
    return {"csrf_token": csrf_token}


@router.post("/forgot-password")
async def forgot_password(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(limit_password_reset),
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, payload.email)
    if user and user.active:
        raw_token = issue_password_reset(db, user)
        background_tasks.add_task(_deliver_password_reset_email, user.email, raw_token)
    return {"message": "If the account exists, password reset instructions have been sent."}


@router.post("/reset-password")
async def complete_password_reset(
    payload: PasswordResetComplete,
    _: None = Depends(limit_password_reset),
    db: Session = Depends(get_db),
):
    if not reset_password(db, payload.token, payload.new_password):
        raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")
    return {"message": "Password has been reset. Please sign in again."}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_active_user)):
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
):
    token = credentials.credentials if credentials else None
    cookie_auth = False
    if token is None and settings.auth_cookie_enabled:
        token = request.cookies.get(settings.auth_cookie_name)
        cookie_auth = token is not None
    if cookie_auth:
        validate_cookie_csrf(request)
    if token:
        try:
            session_id = get_token_payload(token).get("sid")
        except HTTPException:
            session_id = None
        if session_id:
            session = db.query(BrowserSession).filter(BrowserSession.id == session_id).first()
            if session and session.revoked_at is None:
                session.revoked_at = datetime.now(timezone.utc)
                db.commit()
    response.delete_cookie(settings.auth_cookie_name, path="/", secure=settings.auth_cookie_secure, httponly=True, samesite=settings.auth_cookie_samesite.lower())
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.auth_cookie_secure, httponly=True, samesite=settings.auth_cookie_samesite.lower())
    return {"message": "Logged out successfully."}
