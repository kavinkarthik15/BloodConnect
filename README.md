# NSS BloodConnect

NSS BloodConnect is a full-stack blood coordination platform for NSS volunteers, coordinators, donors, and requesters. It helps organizations manage emergency blood requests, identify compatible donors, coordinate responses, and track engagement.

## Key Features

- Secure user authentication with JWT
- Role-based access for requesters, donors, coordinators, and volunteers
- Blood request creation and verification workflow
- Donor profile management and availability tracking
- Compatibility-aware donor matching based on blood group and location
- In-app notification system for accept, decline, and verification events
- Audit trail for operational and compliance events
- AI assistant endpoint for practical guidance and coordination support
- Safety disclaimer preventing misuse as a medical diagnosis tool

## Tech Stack

- Frontend: React + Vite + TypeScript
- Backend: FastAPI + SQLAlchemy + Pydantic
- Database: SQLite for local development; PostgreSQL-ready production configuration
- Auth: JWT + passlib + bcrypt
- Testing: pytest
- Migrations: Alembic

## Project Structure

- `backend/` — FastAPI application, models, schemas, services, and tests
- `backend/alembic/` — Alembic migration scripts
- `frontend/` — React front-end app shell and UI
- `.env.example` — environment variable template
- `docker-compose.yml` — optional local container orchestration
- `DEPLOYMENT.md` — production deployment guidance

## Local Setup

### 1. Create environment file

Copy the example file and adjust values:

```bash
copy .env.example .env
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the API:

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend development server binds to localhost by default. To expose it to
other devices on a trusted LAN, explicitly run `npm run dev:lan`.

## Database and Migrations

Local development may continue using SQLite. For a fresh database:

```bash
cd backend
$env:DATABASE_URL="sqlite:///./tmp_nss_bloodconnect.db"
.venv\Scripts\alembic upgrade head
```

Do not run Alembic against the populated development database. For production,
create a new empty PostgreSQL database and run `alembic upgrade head` exactly
once before normal use.

## Testing

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

## Production Configuration Notes

- Set `APP_ENV=production` and provide a PostgreSQL `DATABASE_URL`.
- Use a strong external `JWT_SECRET`.
- Keep `CORS_ORIGINS` explicit and credential-safe.
- Keep AI credentials on the backend only; do not expose them in browser code.
- Use `GET /health` and `GET /health/ready` for health checks.

## Workflow Summary

1. Register as a requester, donor, or coordinator.
2. Create a blood request and add patient and hospital details.
3. Coordinator verifies the request.
4. Matching service finds likely compatible donors.
5. Donors accept or decline the request.
6. Coordinator completes the case and notifications update stakeholders.

## Important Safety Note

This platform is for coordination and triage support only. It does not diagnose medical conditions, guarantee compatibility, or replace medical evaluation by trained clinicians or blood bank staff.
