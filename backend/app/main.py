from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, version="1.0.0")

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if settings.frontend_url and settings.frontend_url not in origins:
    origins.append(settings.frontend_url)
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
    try:
        from sqlalchemy import text
        from app.db.database import SessionLocal

        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready", "database": "ok"}
    except Exception:
        return {"status": "degraded", "database": "unavailable"}
