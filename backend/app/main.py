from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.ai import legacy_router, router as ai_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.donors import router as donors_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.requests import router as requests_router
from app.api.routes.volunteers import router as volunteers_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.reports import router as reports_router
from app.core.config import settings
from app.db.database import Base, engine
from app.middleware import RequestSizeLimitMiddleware

if settings.app_env.strip().lower() == "test":
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(application: FastAPI):
    redis_client = None
    if settings.rate_limit_redis_url:
        redis_client = Redis.from_url(
            settings.rate_limit_redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        try:
            await redis_client.ping()
        except RedisError:
            await redis_client.aclose()
            raise RuntimeError("Configured rate-limit store is unavailable.") from None
    application.state.redis = redis_client
    try:
        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.app_env.strip().lower() in {"production", "staging"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if settings.frontend_url and settings.frontend_url not in origins:
    origins.append(settings.frontend_url)
if settings.app_env.strip().lower() not in {"production", "staging"}:
    if "http://localhost:5173" not in origins:
        origins.append("http://localhost:5173")
    if "http://127.0.0.1:5173" not in origins:
        origins.append("http://127.0.0.1:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        host.strip()
        for host in settings.trusted_hosts.split(",")
        if host.strip()
    ],
)
app.add_middleware(RequestSizeLimitMiddleware)

app.include_router(auth_router)
app.include_router(donors_router)
app.include_router(requests_router)
app.include_router(volunteers_router)
app.include_router(campaigns_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(audit_router)
app.include_router(ai_router)
app.include_router(legacy_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/health/ready")
async def health_ready():
    from sqlalchemy import text
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
    finally:
        db.close()

    if settings.rate_limit_redis_url:
        redis_client = getattr(app.state, "redis", None)
        if redis_client is None:
            return JSONResponse(status_code=503, content={"status": "degraded", "rate_limit_store": "unavailable"})
        try:
            await redis_client.ping()
        except RedisError:
            return JSONResponse(status_code=503, content={"status": "degraded", "rate_limit_store": "unavailable"})
    return {"status": "ready", "database": "ok", "rate_limit_store": "ok" if settings.rate_limit_redis_url else "not_configured"}
