# NSS BloodConnect Deployment Guide

## Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 15+ for production deployment
- A host or platform such as Render, Fly.io, Railway, or a managed container environment
- Access to environment variables for the platform

## Environment variables

Create a production `.env` file or set the following environment variables in the deployment system:

```env
APP_ENV=production
DATABASE_URL=postgresql://user:password@host:5432/dbname
JWT_SECRET=replace-with-strong-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FRONTEND_URL=https://your-frontend.example.com
BACKEND_URL=https://your-backend.example.com
CORS_ORIGINS=https://your-frontend.example.com
GEOCODING_PROVIDER=nominatim
GEOCODING_USER_AGENT=NSSBloodConnect/1.0
GEOCODING_TIMEOUT_SECONDS=5.0
AI_ENABLED=false
AI_PROVIDER=openai
AI_API_KEY=replace-with-ai-key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=20.0
```

## PostgreSQL

Production deployments should use PostgreSQL rather than SQLite. The application rejects SQLite in production by validation.

### Create database

```bash
createdb bloodconnect
```

## Alembic fresh database procedure

For a new empty database:

```bash
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
```

This creates the schema from the migration chain.

## Vercel architecture

Deploy this repository as two Vercel projects using the same repository:

- Frontend project root: `frontend/`
- Backend project root: `backend/`

The frontend project runs `npm run build` and serves `dist`. Its `vercel.json`
rewrites client-side routes to `index.html` while leaving `/api` paths alone.
The backend project imports the existing FastAPI application through
`backend/api/index.py`; it does not duplicate or move the application.

Configure `VITE_API_BASE_URL` on the frontend project to the deployed backend
URL. Configure the backend's `FRONTEND_URL` and `CORS_ORIGINS` to the deployed
frontend URL.

## Alembic production procedure

Do not run migrations automatically during a serverless request. Before the
first production use, create the new PostgreSQL database and run exactly once
against that empty production database:

```bash
cd backend
python -m alembic upgrade head
```

Do not run this command against the populated development database. Do not use
`stamp` as part of the fresh production setup.

## Frontend build

```bash
cd frontend
npm install
npm run build
```

## Backend production start

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Do not use `--reload` in production.

## AI configuration

The AI assistant is optional and disabled by default. In production, set `AI_ENABLED=true` only when a backend-only AI provider is configured.

- Keep `AI_API_KEY` on the backend server only.
- Do not expose it in a Vite/browser build.
- The frontend calls the backend assistant route, not the external AI provider.

## AI-disabled mode

If `AI_ENABLED=false`, the app responds safely with a controlled unavailable message instead of failing or crashing.

## CORS

Use explicit origins only. Do not use wildcard origins with credentials.

## JWT secret

Set a strong external secret in production and keep it out of source control and browser assets.

## Health checks

```http
GET /health
GET /health/ready
```

These endpoints should not expose database credentials or secret values.

## Database backups

- Schedule regular PostgreSQL backups.
- Keep backups encrypted and retain them according to your operational policy.
- Test restores before using production data for critical decisions.

## Deployment sequence

1. Configure PostgreSQL and environment variables.
2. Run Alembic on the target database.
3. Build the frontend.
4. Start the backend in production mode.
5. Confirm health checks and auth flows.
6. Verify the AI assistant is disabled or properly configured.
7. Test core workflows before public use.

## Rollback considerations

- Keep the previous application image or build artifact available.
- Keep database backups available before any schema change.
- Roll back the application first; database rollback should be handled carefully and intentionally.

## Safety reminder

This project is a coordination tool, not a medical decision engine. It does not determine donor eligibility or transfusion safety. Final medical decisions remain with qualified clinical staff and authorized blood bank operations.
