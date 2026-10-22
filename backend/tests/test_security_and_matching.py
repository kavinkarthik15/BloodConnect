import asyncio
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import jwt

from app.api.routes import auth as auth_routes
from app.core.config import Settings
from app.db.database import Base, SessionLocal
from app.main import app
from app.middleware import (
    MAX_API_REQUEST_BYTES,
    MAX_AUTH_REQUEST_BYTES,
    RequestSizeLimitMiddleware,
)
from app.models.auth_security import BrowserSession, PasswordResetToken
from app.models.blood_request import BloodRequest
from app.models.user import User
from app.models.donor import DonorProfile
from app.models.notification import Notification
from app.schemas.auth import UserRegister
from app.services.auth_service import create_access_token, get_password_hash, get_token_payload
from app.services.blood_request_service import notify_active_coordinators
from app.services.compatibility_service import BLOOD_GROUPS, is_potentially_compatible
from app.cli.provision_user import provision_privileged_user


client = TestClient(app)


def production_jwt_secret():
    return secrets.token_urlsafe(48)


def account(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    response = client.post("/api/auth/register", json={
        "full_name": f"Test {role}",
        "email": email,
        "phone": "9876543210",
        "password": "SafePassword123",
        "role": role,
    })
    return email, response


def seed_privileged(role: str):
    email = f"{role}-{uuid4().hex}@example.com"
    db = SessionLocal()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.close()
        return email
    db.add(User(full_name=f"Test {role}", email=email, phone="9876543210", password_hash=get_password_hash("SafePassword123"), role=role))
    db.commit()
    db.close()
    return email


def token(email: str):
    response = client.post("/api/auth/login", json={"email": email, "password": "SafePassword123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def test_public_registration_only_allows_requester_and_donor():
    assert account("requester")[1].status_code == 201
    assert account("donor")[1].status_code == 201
    assert account("volunteer")[1].status_code == 403
    assert account("coordinator")[1].status_code == 403
    assert account("admin")[1].status_code == 403


def test_default_jwt_secret_is_random_and_not_predictable(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    first = Settings(_env_file=None, app_env="development", database_url="sqlite://")
    second = Settings(_env_file=None, app_env="development", database_url="sqlite://")
    assert len(first.jwt_secret) >= 32
    assert first.jwt_secret != second.jwt_secret


def test_production_requires_an_external_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
        )


def test_production_accepts_jwt_secret_from_environment(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", production_jwt_secret())
    configured = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://db.example/bloodconnect",
        frontend_url="https://app.example.org",
        cors_origins="https://app.example.org",
        trusted_hosts="app.example.org,api.example.org",
        rate_limit_redis_url="rediss://redis.example/0",
        smtp_host="smtp.example.org",
        smtp_from_email="noreply@example.org",
    )
    assert configured.jwt_secret


@pytest.mark.parametrize(
    "jwt_secret",
    [
        "replace-with-strong-random-secret",
        "a" * 48,
        "change-me-" + secrets.token_urlsafe(36),
    ],
)
def test_production_rejects_placeholder_or_low_entropy_jwt_secrets(jwt_secret):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=jwt_secret,
        )


def test_settings_repr_redacts_credentials():
    private_values = (
        "jwt-secret-value-that-must-never-appear",
        "postgresql+psycopg://user:password@db.example/bloodconnect",
        "rediss://redis-user:redis-password@redis.example/0",
        "smtp-user-that-must-never-appear",
        "smtp-password-that-must-never-appear",
        "ai-key-that-must-never-appear",
    )
    configured = Settings(
        _env_file=None,
        jwt_secret=private_values[0],
        database_url=private_values[1],
        rate_limit_redis_url=private_values[2],
        smtp_username=private_values[3],
        smtp_password=private_values[4],
        ai_api_key=private_values[5],
    )
    representation = repr(configured)
    assert all(private_value not in representation for private_value in private_values)


def test_security_headers_are_present_and_hsts_is_production_only(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "development")
    development = client.get("/health")
    assert development.headers["X-Content-Type-Options"] == "nosniff"
    assert development.headers["X-Frame-Options"] == "DENY"
    assert development.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert development.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert "Strict-Transport-Security" not in development.headers

    monkeypatch.setattr(settings, "app_env", "production")
    production = client.get("/health")
    assert production.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_production_cors_requires_explicit_https_frontend_origin():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=production_jwt_secret(),
            frontend_url="https://app.example.org",
            cors_origins="https://other.example.org",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=production_jwt_secret(),
            frontend_url="https://app.example.org",
            cors_origins="https://app.example.org,http://localhost:5173",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=production_jwt_secret(),
            frontend_url="https://app.example.org",
            cors_origins="https://app.example.org/path",
        )
    valid = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://db.example/bloodconnect",
        jwt_secret=production_jwt_secret(),
        frontend_url="https://app.example.org",
        cors_origins="https://app.example.org,https://api.example.org",
        trusted_hosts="app.example.org,api.example.org",
        rate_limit_redis_url="rediss://redis.example/0",
        smtp_host="smtp.example.org",
        smtp_from_email="noreply@example.org",
    )
    assert "http://localhost:5173" not in valid.cors_origins
    assert valid.auth_cookie_enabled is False


@pytest.mark.parametrize(
    "trusted_hosts",
    [
        "",
        "*",
        "app.example.org:443",
        "https://app.example.org",
        "app.example.org/path",
        "app.example.org bad.example.org",
        "app..example.org",
    ],
)
def test_production_requires_explicit_hostname_only_trusted_hosts(trusted_hosts):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=production_jwt_secret(),
            frontend_url="https://app.example.org",
            cors_origins="https://app.example.org",
            trusted_hosts=trusted_hosts,
            rate_limit_redis_url="rediss://redis.example/0",
            smtp_host="smtp.example.org",
            smtp_from_email="noreply@example.org",
        )


def test_production_accepts_explicit_trusted_hostnames():
    configured = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+psycopg://db.example/bloodconnect",
        jwt_secret=production_jwt_secret(),
        frontend_url="https://app.example.org",
        cors_origins="https://app.example.org",
        trusted_hosts="app.example.org,api.example.org",
        rate_limit_redis_url="rediss://redis.example/0",
        smtp_host="smtp.example.org",
        smtp_from_email="noreply@example.org",
    )
    assert configured.trusted_hosts == "app.example.org,api.example.org"


def test_trusted_host_middleware_rejects_unlisted_hosts():
    from fastapi import FastAPI
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    assert any(middleware.cls is TrustedHostMiddleware for middleware in app.user_middleware)

    trusted_app = FastAPI()
    trusted_app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["api.example.org"],
    )

    with TestClient(trusted_app) as trusted_client:
        assert trusted_client.get("/", headers={"Host": "api.example.org"}).status_code == 404
        assert trusted_client.get("/", headers={"Host": "untrusted.example.org"}).status_code == 400


def test_authentication_request_body_size_is_limited():
    response = client.post(
        "/api/auth/login",
        content=b"x" * (MAX_AUTH_REQUEST_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."


def test_json_api_request_body_size_is_limited():
    response = client.post(
        "/api/ai/chat",
        content=b"x" * (MAX_API_REQUEST_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."


def test_request_size_limit_applies_to_chunked_bodies_without_content_length():
    sent_messages = []
    chunks = [b"x" * (MAX_AUTH_REQUEST_BYTES // 2)] * 3

    async def receive():
        if chunks:
            chunk = chunks.pop(0)
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": bool(chunks),
            }
        return {"type": "http.disconnect"}

    async def send(message):
        sent_messages.append(message)

    async def unused_app(_scope, _receive, _send):
        raise AssertionError("Oversized request reached the application.")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8000),
    }

    asyncio.run(
        RequestSizeLimitMiddleware(unused_app)(scope, receive, send)
    )

    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 413


def test_production_cookie_sessions_require_secure_transport():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://db.example/bloodconnect",
            jwt_secret=production_jwt_secret(),
            frontend_url="https://app.example.org",
            cors_origins="https://app.example.org",
            rate_limit_redis_url="rediss://redis.example/0",
            smtp_host="smtp.example.org",
            smtp_from_email="noreply@example.org",
            auth_cookie_enabled=True,
            auth_cookie_secure=False,
        )


@pytest.mark.parametrize("password", ["short", "a" * 73, "é" * 37])
def test_registration_rejects_weak_or_bcrypt_oversized_passwords(password):
    with pytest.raises(ValidationError):
        UserRegister(
            full_name="Test User",
            email="test@example.org",
            phone="9876543210",
            password=password,
        )


def test_registration_accepts_password_at_policy_limits():
    user = UserRegister(
        full_name="Test User",
        email="test@example.org",
        phone="9876543210",
        password="SafePassword123",
    )
    assert user.password == "SafePassword123"


def test_new_request_notifications_target_each_active_coordinator():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    active = [
        User(full_name=f"Coordinator {index}", email=f"coordinator-{index}@example.org", phone="9876543210", password_hash="hash", role="coordinator", active=True)
        for index in (10, 11)
    ]
    inactive = User(full_name="Inactive coordinator", email="inactive@example.org", phone="9876543210", password_hash="hash", role="coordinator", active=False)
    db.add_all([*active, inactive])
    db.commit()

    assert notify_active_coordinators(db, BloodRequest(id=22, request_code="BCR-test")) == 2
    notifications = db.query(Notification).order_by(Notification.user_id).all()
    assert [item.user_id for item in notifications] == [item.id for item in active]

    for coordinator in active:
        coordinator.active = False
    db.commit()
    assert notify_active_coordinators(db, BloodRequest(id=23, request_code="BCR-test-2")) == 0
    assert db.query(Notification).count() == 2
    db.close()
    engine.dispose()


class FakeRedis:
    def __init__(self):
        self.counts = {}

    async def eval(self, _script, _key_count, key, _window_ms):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key], 60_000


class BrokenRedis:
    async def eval(self, *_args):
        raise RedisError("redis unavailable")


def test_login_and_registration_return_429_after_rate_limits():
    existing_email, response = account("requester")
    assert response.status_code == 201
    original_redis = getattr(app.state, "redis", None)
    app.state.redis = FakeRedis()
    try:
        for _ in range(5):
            assert client.post("/api/auth/login", json={
                "email": "missing@example.org",
                "password": "SafePassword123",
            }).status_code == 401
        limited_login = client.post("/api/auth/login", json={
            "email": "missing@example.org",
            "password": "SafePassword123",
        })
        assert limited_login.status_code == 429
        assert limited_login.headers["Retry-After"]

        for _ in range(5):
            assert client.post("/api/auth/register", json={
                "full_name": "Duplicate User",
                "email": existing_email,
                "phone": "9876543210",
                "password": "SafePassword123",
                "role": "requester",
            }).status_code == 400
        limited_registration = client.post("/api/auth/register", json={
            "full_name": "Duplicate User",
            "email": existing_email,
            "phone": "9876543210",
            "password": "SafePassword123",
            "role": "requester",
        })
        assert limited_registration.status_code == 429
    finally:
        app.state.redis = original_redis


def test_rate_limit_store_failure_returns_503():
    original_redis = getattr(app.state, "redis", None)
    app.state.redis = BrokenRedis()
    try:
        response = client.post("/api/auth/login", json={
            "email": "missing@example.org",
            "password": "SafePassword123",
        })
        assert response.status_code == 503
    finally:
        app.state.redis = original_redis


def test_password_reset_is_private_expiring_and_single_use():
    email, response = account("requester")
    assert response.status_code == 201
    old_token = token(email)
    with patch.object(auth_routes, "send_password_reset_email") as send_email:
        known = client.post("/api/auth/forgot-password", json={"email": email})
        unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.org"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    send_email.assert_called_once()
    reset_token = send_email.call_args.args[1]

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    stored_reset = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).one()
    assert stored_reset.token_hash != reset_token
    active_sessions = db.query(BrowserSession).filter(
        BrowserSession.user_id == user.id,
        BrowserSession.revoked_at.is_(None),
    ).count()
    assert active_sessions == 1
    db.close()

    changed = client.post("/api/auth/reset-password", json={
        "token": reset_token,
        "new_password": "AnotherSafePass123",
    })
    assert changed.status_code == 200
    assert client.post("/api/auth/reset-password", json={
        "token": reset_token,
        "new_password": "ThirdSafePass123",
    }).status_code == 400
    assert client.get("/api/auth/me", headers=headers(old_token)).status_code == 401
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    assert db.query(BrowserSession).filter(
        BrowserSession.user_id == user.id,
        BrowserSession.revoked_at.is_(None),
    ).count() == 0
    db.close()
    assert client.post("/api/auth/login", json={
        "email": email,
        "password": "AnotherSafePass123",
    }).status_code == 200

    with patch.object(auth_routes, "send_password_reset_email") as send_email:
        assert client.post("/api/auth/forgot-password", json={"email": email}).status_code == 200
    expired_token = send_email.call_args.args[1]
    db = SessionLocal()
    expired_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.consumed_at.is_(None),
    ).one()
    expired_record.expires_at = expired_record.created_at
    db.commit()
    db.close()
    assert client.post("/api/auth/reset-password", json={
        "token": expired_token,
        "new_password": "ExpiredResetPass123",
    }).status_code == 400


def test_password_reset_delivery_failure_keeps_generic_response(caplog):
    email, response = account("requester")
    assert response.status_code == 201
    with patch.object(
        auth_routes,
        "send_password_reset_email",
        side_effect=smtplib.SMTPException("provider details must not be logged"),
    ):
        reset_response = client.post("/api/auth/forgot-password", json={"email": email})
    assert reset_response.status_code == 200
    assert reset_response.json() == {
        "message": "If the account exists, password reset instructions have been sent."
    }
    assert email not in caplog.text
    assert "provider details must not be logged" not in caplog.text


def test_cookie_session_requires_csrf_and_logout_revokes_session():
    original_cookie_setting = auth_routes.settings.auth_cookie_enabled
    auth_routes.settings.auth_cookie_enabled = True
    email, response = account("requester")
    assert response.status_code == 201
    try:
        rejected_origin = client.post(
            "/api/auth/login",
            json={"email": email, "password": "SafePassword123"},
            headers={"Origin": "https://untrusted.example.org"},
        )
        assert rejected_origin.status_code == 403
        login_response = client.post("/api/auth/login", json={
            "email": email,
            "password": "SafePassword123",
        }, headers={"Origin": "http://localhost:5173"})
        assert login_response.status_code == 200
        assert "httponly" in login_response.headers["set-cookie"].lower()
        assert login_response.json()["access_token"] is None
        assert client.get("/api/auth/me").status_code == 200
        assert client.post("/api/auth/logout").status_code == 403
        csrf_value = client.cookies.get(auth_routes.settings.csrf_cookie_name)
        rejected_logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_value, "Origin": "https://untrusted.example.org"},
        )
        assert rejected_logout.status_code == 403
        logged_out = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_value, "Origin": "http://localhost:5173"},
        )
        assert logged_out.status_code == 200
        assert client.get("/api/auth/me").status_code == 401
    finally:
        auth_routes.settings.auth_cookie_enabled = original_cookie_setting
        client.cookies.clear()


def test_bearer_logout_revokes_new_session():
    email, response = account("requester")
    assert response.status_code == 201
    access_token = token(email)
    session_id = get_token_payload(access_token)["sid"]
    logout_response = client.post("/api/auth/logout", headers=headers(access_token))
    assert logout_response.status_code == 200
    assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 401
    db = SessionLocal()
    session = db.query(BrowserSession).filter(BrowserSession.id == session_id).one()
    assert session.revoked_at is not None
    db.close()


def test_generated_access_tokens_preserve_hs256_contract():
    email, response = account("requester")
    assert response.status_code == 201

    access_token = token(email)
    claims = jwt.decode(
        access_token,
        auth_routes.settings.jwt_secret,
        algorithms=["HS256"],
    )

    assert jwt.get_unverified_header(access_token)["alg"] == "HS256"
    assert claims["sub"] == email
    assert claims["sid"]
    assert claims["exp"] > datetime.now(timezone.utc).timestamp()
    assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 200


def test_protected_route_rejects_tokens_without_a_valid_session_id():
    email, response = account("requester")
    assert response.status_code == 201
    with pytest.raises(TypeError):
        create_access_token(email)

    missing_session = jwt.encode(
        {
            "sub": email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        auth_routes.settings.jwt_secret,
        algorithm=auth_routes.settings.jwt_algorithm,
    )
    unknown_session = create_access_token(email, session_id=str(uuid4()))

    assert client.get("/api/auth/me", headers=headers(missing_session)).status_code == 401
    assert client.get("/api/auth/me", headers=headers(unknown_session)).status_code == 401


def test_protected_route_rejects_malformed_tampered_and_wrong_algorithm_tokens(monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "jwt_secret", "synthetic-test-secret-" * 4)
    email, response = account("requester")
    assert response.status_code == 201
    access_token = token(email)
    claims = get_token_payload(access_token)

    wrong_algorithm = jwt.encode(
        claims,
        auth_routes.settings.jwt_secret,
        algorithm="HS512",
    )
    token_parts = access_token.split(".")
    tampered_signature = token_parts[2][:-1] + (
        "A" if token_parts[2][-1] != "A" else "B"
    )
    tampered = ".".join((*token_parts[:2], tampered_signature))

    for invalid_token in ("not.a.jwt", tampered, wrong_algorithm):
        assert client.get(
            "/api/auth/me",
            headers=headers(invalid_token),
        ).status_code == 401


def test_protected_route_rejects_expired_access_token():
    email, response = account("requester")
    assert response.status_code == 201
    active_token = token(email)
    session_id = get_token_payload(active_token)["sid"]
    expired_token = create_access_token(
        email,
        expires_delta=timedelta(seconds=-1),
        session_id=session_id,
    )

    assert client.get("/api/auth/me", headers=headers(expired_token)).status_code == 401


def test_protected_route_rejects_expired_browser_session():
    email, response = account("requester")
    assert response.status_code == 201
    access_token = token(email)
    session_id = get_token_payload(access_token)["sid"]

    db = SessionLocal()
    session = db.query(BrowserSession).filter(BrowserSession.id == session_id).one()
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()

    assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 401


def test_protected_route_rejects_deleted_browser_session():
    email, response = account("requester")
    assert response.status_code == 201
    access_token = token(email)
    session_id = get_token_payload(access_token)["sid"]

    db = SessionLocal()
    db.query(BrowserSession).filter(BrowserSession.id == session_id).delete()
    db.commit()
    db.close()

    assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 401


def test_bearer_login_remains_available_during_cookie_transition():
    original_cookie_setting = auth_routes.settings.auth_cookie_enabled
    auth_routes.settings.auth_cookie_enabled = True
    email, response = account("requester")
    assert response.status_code == 201
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": email, "password": "SafePassword123"},
            headers={"X-Auth-Mode": "bearer"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        assert access_token
        assert auth_routes.settings.auth_cookie_name not in login_response.headers.get("set-cookie", "")
        assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 200
        assert client.post("/api/auth/logout", headers=headers(access_token)).status_code == 200
        assert client.get("/api/auth/me", headers=headers(access_token)).status_code == 401
    finally:
        auth_routes.settings.auth_cookie_enabled = original_cookie_setting
        client.cookies.clear()


def test_privileged_provisioning_is_limited_to_trusted_roles():
    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            provision_privileged_user(
                db,
                full_name="Test User",
                email=f"provision-{uuid4().hex}@example.org",
                phone="9876543210",
                password="SafePassword123",
                role="admin",
            )
        user = provision_privileged_user(
            db,
            full_name="Provisioned Volunteer",
            email=f"provision-{uuid4().hex}@example.org",
            phone="9876543210",
            password="SafePassword123",
            role="volunteer",
        )
        assert user.role == "volunteer"
        assert user.active is True
    finally:
        db.close()


def test_compatibility_rules_are_looked_up_from_recipient_to_donor():
    compatible_donors_by_recipient = {
        "O-": {"O-"},
        "O+": {"O-", "O+"},
        "A-": {"O-", "A-"},
        "A+": {"O-", "O+", "A-", "A+"},
        "B-": {"O-", "B-"},
        "B+": {"O-", "O+", "B-", "B+"},
        "AB-": {"O-", "A-", "B-", "AB-"},
        "AB+": set(BLOOD_GROUPS),
    }
    for required_group, expected_donors in compatible_donors_by_recipient.items():
        for donor_group in BLOOD_GROUPS:
            assert is_potentially_compatible(donor_group, required_group) == (
                donor_group in expected_donors
            )


def test_unmatched_donor_cannot_accept_or_decline():
    requester, requester_response = account("requester")
    donor, donor_response = account("donor")
    coordinator = seed_privileged("coordinator")
    assert requester_response.status_code == 201
    assert donor_response.status_code == 201

    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Unmatched Test",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Test Hospital",
        "hospital_address": "1 Test Street",
        "city": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "required_at": "2027-09-25T12:00:00",
        "urgency": "Urgent",
        "contact_name": "Test Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    coordinator_headers = headers(token(coordinator))
    assert client.post(f"/api/requests/{request_id}/verify", headers=coordinator_headers).status_code == 200

    donor_id = client.get("/api/auth/me", headers=headers(token(donor))).json()["id"]
    db = SessionLocal()
    db.add(DonorProfile(user_id=donor_id, blood_group="O+", city="Hyderabad", area="Madhapur", latitude=17.4, longitude=78.4, available=True, verified=True))
    db.commit()
    db.close()

    donor_headers = headers(token(donor))
    assert client.post(f"/api/requests/{request_id}/accept", headers=donor_headers).status_code == 403
    assert client.post(f"/api/requests/{request_id}/decline", headers=donor_headers).status_code == 403


def test_matching_without_coordinates_returns_no_fake_distance(monkeypatch):
    requester, _ = account("requester")
    coordinator = seed_privileged("coordinator")
    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Location Test",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Test Hospital",
        "hospital_address": "Unknown",
        "city": "Unknown",
        "required_at": "2027-09-25T12:00:00",
        "urgency": "Normal",
        "contact_name": "Test Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    assert client.post(f"/api/requests/{request_id}/verify", headers=headers(token(coordinator))).status_code == 200
    result = client.post(f"/api/requests/{request_id}/match", headers=headers(token(coordinator)))
    assert result.status_code == 200
    assert result.json() == {"matched_count": 0, "matches": []}


def test_donor_cannot_self_verify_but_coordinator_can():
    donor, response = account("donor")
    assert response.status_code == 201
    donor_token = token(donor)
    profile = client.post("/api/donors/me", headers=headers(donor_token), json={"blood_group": "O+", "city": "Bengaluru", "verified": True})
    assert profile.status_code == 200
    assert profile.json()["verified"] is False

    coordinator = seed_privileged("coordinator")
    donor_id = profile.json()["user_id"]
    assert client.get("/api/donors/management", headers=headers(donor_token)).status_code == 403
    assert client.patch(
        f"/api/donors/management/{donor_id}/verification?verified=true",
        headers=headers(donor_token),
    ).status_code == 403
    verified = client.patch(f"/api/donors/management/{donor_id}/verification?verified=true", headers=headers(token(coordinator)))
    assert verified.status_code == 200
    assert verified.json()["verified"] is True


def test_notifications_are_private_and_unread_count_is_scoped():
    first, first_response = account("requester")
    second, second_response = account("requester")
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    db = SessionLocal()
    first_id = db.query(User).filter(User.email == first).first().id
    second_id = db.query(User).filter(User.email == second).first().id
    db.add_all([
        Notification(user_id=first_id, type="system", title="Private one", message="One"),
        Notification(user_id=second_id, type="system", title="Private two", message="Two"),
    ])
    db.commit()
    db.close()
    first_token = token(first)
    assert client.get("/api/notifications", headers=headers(first_token)).json()[0]["title"] == "Private one"
    assert client.get("/api/notifications/unread-count", headers=headers(first_token)).json()["count"] == 1
    second_notification = client.get("/api/notifications", headers=headers(token(second))).json()[0]
    assert client.patch(f"/api/notifications/{second_notification['id']}/read", headers=headers(first_token)).status_code == 404


def test_map_endpoint_is_coordinator_only():
    requester, response = account("requester")
    assert response.status_code == 201
    request = client.post("/api/requests", headers=headers(token(requester)), json={
        "patient_reference": "Map privacy test", "blood_group": "O+", "units_required": 1,
        "hospital_name": "Map Hospital", "hospital_address": "1 Map Street", "city": "Bengaluru",
        "latitude": 12.9716, "longitude": 77.5946, "required_at": "2027-09-25T12:00:00",
        "urgency": "Normal", "contact_name": "Contact", "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    assert client.get(f"/api/requests/{request_id}/coordination-map", headers=headers(token(requester))).status_code == 403
    assert client.get("/api/coordinator/reports", headers=headers(token(requester))).status_code == 403


def test_requester_cannot_read_or_change_another_users_request():
    owner, owner_response = account("requester")
    other, other_response = account("requester")
    assert owner_response.status_code == other_response.status_code == 201
    request = client.post("/api/requests", headers=headers(token(owner)), json={
        "patient_reference": "Ownership check",
        "blood_group": "O+",
        "units_required": 1,
        "hospital_name": "Test Hospital",
        "hospital_address": "1 Test Street",
        "city": "Bengaluru",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "required_at": "2027-09-25T12:00:00",
        "urgency": "Normal",
        "contact_name": "Test Contact",
        "contact_phone": "9876543210",
    })
    assert request.status_code == 200
    request_id = request.json()["id"]
    other_headers = headers(token(other))

    assert client.get(f"/api/requests/{request_id}", headers=other_headers).status_code == 403
    assert client.put(
        f"/api/requests/{request_id}",
        headers=other_headers,
        json={"notes": "Unauthorized change"},
    ).status_code == 403
    assert client.post(f"/api/requests/{request_id}/cancel", headers=other_headers).status_code == 403