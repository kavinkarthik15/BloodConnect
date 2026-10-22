# NSS BloodConnect — Project Context for AI Assistants

Use this document as a compact but detailed orientation to the repository. It describes the product intent and the implementation that is actually present in the code. When making changes, verify behavior in the source and tests rather than treating this document as a substitute for them.

## 1. Project at a glance

NSS BloodConnect is a web-based blood-donation coordination platform intended to connect people requesting blood with potentially compatible, available donors, with National Service Scheme (NSS) coordinators and volunteers supporting verification and operational follow-up.

The product organizes requests, donor availability and responses, volunteer assignments, donation campaigns, notifications, operational reports, and an optional AI help assistant. It is a coordination tool—not a blood bank, clinical system, eligibility checker, transfusion decision system, or emergency-care service. Matching results are potential matches only and must not be treated as a guarantee of donor eligibility or transfusion compatibility. Qualified clinicians and authorized blood bank staff make medical decisions.

## 2. People and permissions

The application uses four roles:

- **Requester** — creates and tracks their own blood requests.
- **Donor** — maintains a donor profile and availability, reviews matched requests, and accepts or declines.
- **Volunteer** — views and progresses assignments made by a coordinator.
- **Coordinator** — privileged operational role for verifying requests and donors, matching donors, managing volunteers and campaigns, and viewing reports and audit events.

Public registration is deliberately restricted to `requester` and `donor`. Coordinator and volunteer accounts must be provisioned through a trusted administrative process; public sign-up cannot select those roles. The frontend also restricts pages according to role, but API dependencies enforce authorization and are the actual security boundary.

Authentication uses a bearer JWT. Passwords are hashed using passlib/bcrypt. The frontend stores the access token in `localStorage` under `nss-bloodconnect-token`, then sends it in the `Authorization` header. `GET /api/auth/me` restores the signed-in profile on page load. The logout endpoint returns a success message; client logout removes the stored token.

## 3. Main user journey

1. A requester registers/signs in and submits a request with patient reference, requested blood group and units, hospital/location, deadline, urgency, and contact details.
2. The request begins with status `submitted`. The backend generates a request code and attempts to geocode the hospital address and city if coordinates were not supplied. A new-request notification is created for each active coordinator; if there are no active coordinators, request creation still succeeds and no notification is queued.
3. A coordinator reviews and verifies the request. Verification records who verified it and when, adds an audit event, and notifies the requester.
4. A coordinator can run donor matching on a verified request; a volunteer can do so only while actively assigned to that request. Matching uses verified, available donor profiles and the existing blood-group lookup. When both request and donor coordinates exist, candidates outside the default 25 km radius are excluded and a distance is stored. If either coordinate pair is unavailable, same-city matching is used and distance remains `null`; the application does not invent a distance. Matching and its recipient-scoped donor notifications commit together.
5. A matched donor can accept or decline once while the request is `verified`, `coordinating`, or `partially_fulfilled`. Multiple donors can respond to one request. Acceptance is an offer to coordinate only: it does not imply a clinically verified donation, reduce outstanding units, or fulfill the request. Each request/donor match and response pair is unique. Donors may withdraw their own accepted response while a request is open and before that donor's outcome has been confirmed.
6. Request states are `submitted` → `verified` → `coordinating` → `partially_fulfilled` → `fulfilled`; a request can also become `cancelled`, `closed`, or `expired`. The request stores `units_required` separately from `units_confirmed`. A coordinator-only confirmation endpoint records donor, confirming coordinator, confirmed units, verification source, timestamp, optional reference/notes, and audit event. Confirmed units cannot exceed requested units. Fulfillment is set only when confirmed units reach requested units. This records a verified donation outcome and does not assert that a unit was transfused. The legacy completion endpoint no longer marks requests fulfilled without these records.
7. Requesters may cancel only their own open requests before any units are confirmed. Coordinators may cancel open requests with no confirmed units or close an open case; a case with confirmed units should be closed rather than cancelled. Open requests expire at `required_at`; API access enforces expiration lazily and operations must also schedule `python -m app.cli.expire_requests` from `backend/` to expire cases without traffic. Emergency requests carry an immediate `emergency` escalation flag; reaching the deadline sets `overdue` or `emergency_overdue`. These are operational indicators, not medical triage or a guarantee of blood availability.
8. Separately, a coordinator may assign a volunteer to a request. Assignment status progresses through `assigned` → `accepted` → `in_progress` → `completed`; a coordinator can cancel an assignment while it is active. Assignments have their own timestamps and notifications.

Campaigns are an adjacent feature: coordinators create campaigns (initially `planned`) and change status among `planned`, `published`, `completed`, and `cancelled`. Published campaigns can be viewed publicly. Campaign records include location/date and participation, registered-donor, and units-recorded counters.

## 4. Features

- Account registration, login, current-user profile, role-based dashboards and access control.
- Request submission, requester-scoped viewing/updating/cancellation, coordinator verification, multi-donor responses, deadline expiration, coordinator-controlled donation outcome confirmation, and confirmed-unit accounting.
- Donor profile and availability management; coordinator donor search/filtering and donor verification.
- Blood-group and distance-based potential-donor matching, match summaries, and map-oriented coordination data.
- Donor accept/decline responses and response history.
- Coordinator-to-volunteer assignments with controlled state transitions.
- Public campaign listing/details and coordinator campaign management.
- Per-user notifications, unread counts, and read/read-all operations.
- Coordinator analytics, operational reports, and paginated/filterable audit-log access.
- Optional authenticated AI assistant with role-context data and explicit medical-boundary refusals.
- Liveness and database-readiness endpoints: `GET /health` and `GET /health/ready`.

## 5. Technology and architecture

### Frontend

- React 18, TypeScript, and Vite.
- Leaflet / React Leaflet for map presentation.
- The active app entry is `frontend/index.html` → `frontend/src/main.tsx` → `frontend/src/App.tsx`.
- The UI is a single-page application with route selection implemented in `App.tsx` using browser history and `popstate`, rather than a routing library.
- It calls the backend directly using `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.
- `App.tsx` contains the landing/auth flows, role dashboards, request and donor workflows, coordinator pages, campaigns, notifications, reports, and assistant UI.

### Backend

- FastAPI application, Pydantic v2 request/response schemas, and SQLAlchemy ORM.
- Main app: `backend/app/main.py`; API route modules: `backend/app/api/routes/`; business logic: `backend/app/services/`.
- API route prefixes:
  - `/api/auth` — registration, login, current user, logout.
  - `/api/requests` — request lifecycle, matching, maps, donor responses, verification, fulfillment.
  - `/api/donors` — donor profile, availability, donor matches/history, coordinator donor management.
  - `/api/volunteers` — assignments and volunteer status changes.
  - `/api/campaigns` — public campaign viewing and coordinator management.
  - `/api/coordinator` — analytics and reports.
  - `/api/notifications` — user notifications.
  - `/api/audit-logs` — coordinator audit-log search.
  - `/api/assistant/chat` — AI assistant; `/api/ai/chat` is a legacy alias.
- `backend/api/index.py` exposes the FastAPI application for the documented Vercel backend setup.

### Persistence and integrations

- SQLite is the local default (`sqlite:///./nss_bloodconnect.db`); PostgreSQL is intended for production and SQLite is rejected when `APP_ENV=production`.
- Alembic migrations are in `backend/alembic/`. Run the migration chain against a new, empty PostgreSQL database before deployment; do not run it against the populated development database. Revision `002_align_schema_with_models` upgrades databases already at `001_initial_schema` and refuses to proceed if it detects data that would violate the new constraints.
- `Base.metadata.create_all()` runs only when `APP_ENV=test`; production schema changes are managed through reviewed Alembic migrations.
- Address lookup uses OpenStreetMap Nominatim when `GEOCODING_PROVIDER=nominatim`, with a configurable user agent and timeout.
- AI is disabled by default. When enabled, `AIService` calls a configured chat-completions-compatible provider from the backend; provider credentials must not be placed in frontend code.
- Configuration is read from environment variables and `.env` by `backend/app/core/config.py`. Production validation requires PostgreSQL, a strong external JWT secret, and explicit CORS origins.
- New public registrations require passwords of at least 12 characters and no more than 72 UTF-8 bytes; this does not alter existing password hashes. Production CORS requires HTTPS origins and an explicit `FRONTEND_URL`; localhost origins are only added outside production.
- New-request notifications are sent to every active coordinator rather than a fixed user ID. If no active coordinator exists, request creation succeeds without a queued notification.
- Login, registration, reset requests, AI chat, and donor matching have shared Redis rate limits. Production requires Redis and SMTP configuration; Redis failures return `503` instead of failing open.
- Password recovery uses expiring, single-use hashed tokens and a generic response to prevent account enumeration. The SMTP message contains the raw token only in the email's URL fragment; token contents and account addresses are not logged.
- Coordinator/volunteer creation is available only through the operations CLI `python -m app.cli.provision_user`; public signup remains limited to requester/donor.
- Cookie authentication is additive to bearer auth and disabled by default. When explicitly enabled, the auth cookie is HttpOnly, CSRF is double-submit plus Origin-validated, and sessions can be revoked. Production must keep cookies disabled until HTTPS/domain deployment is verified.
- Migration `003_auth_security` adds session and password-reset token tables. It is forward-only reviewed and must not be applied to a populated database without explicit approval and a verified backup.
- Migration `004_request_lifecycle` adds confirmed-unit accounting and donation confirmation records, marks existing fulfilled requests as legacy/unverified without changing their status, maps legacy accepted states to `coordinating`, and adds request/donor uniqueness and foreign keys. It fails fast on duplicate/orphan match or response pairs and is forward-only because downgrade would discard confirmation data. Test on disposable databases; never migrate a populated database without explicit approval and verified backup.
- PostgreSQL request mutations use row-level locks plus database constraints for concurrency. SQLite lifecycle writes are serialized only within one application process for development/test stability; this is not sufficient for multiple workers. Production must use PostgreSQL.

## 6. Data model

The SQLAlchemy models are under `backend/app/models/`:

- **User (`users`)** — identity, email, phone, password hash, role, active flag, organization/NSS unit, timestamps.
- **DonorProfile (`donor_profiles`)** — user, blood group, city/area, optional coordinates, availability, last donation date, coordinator-controlled verification.
- **BloodRequest (`blood_requests`)** — generated request code, requester, patient reference, requested blood group/units, separately confirmed units, hospital/address/city and optional coordinates, required time, urgency/escalation status, contact details, notes, request status, verification/fulfillment metadata, and legacy-unverified fulfillment flag.
- **DonorMatch (`donor_matches`)** — request/donor pair, compatibility label, distance, score, status, creation time.
- **DonorResponse (`donor_responses`)** — unique donor response per request (`accepted`, `declined`, or `withdrawn`), timestamp, optional notes.
- **DonationConfirmation (`donation_confirmations`)** — one coordinator-confirmed donation outcome per request/donor, confirmed units, confirming coordinator, verification source, optional reference/notes, and timestamp.
- **VolunteerAssignment (`volunteer_assignments`)** — request, volunteer, assigning coordinator, status, notes, and lifecycle timestamps.
- **Campaign (`campaigns`)** — title, description, location/date, organizer, status, and impact counters.
- **Notification (`notifications`)** — recipient, type, title/message, related entity, read state, timestamp.
- **AuditLog (`audit_logs`)** — optional actor, action, entity type/id, metadata, optional IP address, timestamp.

The models mostly represent references using integer IDs; do not assume every reference has a database-level foreign-key constraint. Volunteer assignments and audit actors define explicit foreign keys.

## 7. Matching and safety logic

- Supported blood group labels are `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, and `O-`.
- Compatibility lookup is implemented in `backend/app/services/compatibility_service.py`; matching and Haversine distance/score calculation are in `backend/app/services/matching_service.py`.
- Only donor profiles marked both `available` and `verified` are candidates. Matching excludes candidates beyond 25 km when both coordinate pairs are present; otherwise it falls back to same-city matching without a distance value.
- The score combines a blood-group component (higher for an exact group) and a distance component; it is a prioritization heuristic, not clinical validation.
- Do not expand the product into medical eligibility, diagnosis, treatment, clinical triage, or transfusion-safety recommendations. Preserve the warning that a clinician or authorized blood bank makes final decisions.
- The AI service refuses a set of medical-decision questions and its system prompt constrains responses to app guidance and general awareness. Keep AI keys backend-only and preserve safe behavior when AI is disabled/unavailable.

## 8. Frontend screen map

Public pages include `/`, `/login`, `/register`, `/about`, `/awareness`, `/campaigns`, and `/campaigns/:id`.

Authenticated areas include:

- Requester: `/dashboard/requester`, `/requests/create`, `/requests/my`, `/requests/:id`.
- Donor: `/dashboard/donor`, `/donor/profile`, `/donor/requests`, `/donor/requests/:id`, `/donor/accepted`, `/donor/history`.
- Volunteer: `/dashboard/volunteer`, `/volunteer/assigned`, `/volunteer/requests`, `/volunteer/requests/:id`.
- Coordinator: `/dashboard/coordinator`, `/coordinator/verification`, `/coordinator/requests`, `/coordinator/requests/:id`, `/coordinator/donors`, `/coordinator/volunteers`, `/coordinator/campaigns`, `/coordinator/campaigns/create`, `/coordinator/campaigns/:id`, `/coordinator/analytics`, `/coordinator/reports`.
- Shared: `/notifications`, `/profile`, `/ai-assistant`.

Route handling is custom code in `frontend/src/App.tsx`; check its role guards when adding pages. The backend authorization must also be updated/tested when adding protected API operations.

## 9. Tests and local development

- Backend tests use pytest and FastAPI `TestClient`; current suites cover the core workflow, matching/access constraints, volunteer assignments, audit behavior, and AI safety/configuration behavior.
- Phase 3 development-milestone validation: the complete backend suite passed (**50 passed, 0 failed**); the frontend production build passed; TypeScript validation (`npx.cmd tsc --noEmit`) passed; and Alembic migration 004 passed fresh and representative-legacy upgrade checks on disposable SQLite databases. The disposable checks confirmed legacy fulfilled requests remain marked unverified, representative request/response/match data is preserved, and the new uniqueness, foreign-key, and unit constraints are enforced. No populated database was migrated.
- Production-readiness work remains separate from core feature completion. Before public deployment, validate the selected hosting architecture, production secret and proxy configuration, backup/restore procedures, scheduled expiry execution and monitoring, browser end-to-end behavior, and keyboard/screen-reader accessibility. Donation verification is coordinator-entered and is not independently integrated with an authorized blood bank or clinician.
- Run backend tests from `backend/`: `python -m pytest -q`.
- Run the frontend in development from `frontend/`: `npm install`, then `npm run dev`.
- Build the frontend from `frontend/`: `npm run build`.
- Local backend start from `backend/`: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Optional local container setup is in `docker-compose.yml`. Deployment guidance is in `DEPLOYMENT.md`.

## 10. Repository orientation and implementation notes

- `README.md` is the product/setup overview; `DEPLOYMENT.md` describes production configuration and deployment.
- `backend/app/api/deps.py` provides authenticated-user and role dependencies.
- `backend/app/schemas/` defines API payloads; `backend/app/services/` contains reusable domain operations.
- `backend/tests/` contains the backend workflow tests.
- The active frontend is React + TypeScript. There are also Svelte/Vite-template remnants (`App.svelte`, `main.ts`, `Counter.svelte`, and a Svelte config/TypeScript config). The HTML entry points to `main.tsx`, and `vite.config.ts` uses the React plugin. Treat those Svelte files and the generic Svelte frontend README as scaffolding unless the build configuration is deliberately changed.
- The current frontend is concentrated in a large `App.tsx`; follow its existing conventions or make a focused extraction when a change genuinely benefits from one.
- The application currently defines only requester, donor, coordinator, and volunteer roles. There is no administrator role, administrator dashboard, or administrator-specific API authorization. Any administrator dashboard proposal is design-only until its purpose, permissions, trusted provisioning, and backend security boundary are explicitly approved.
- The coordinator audit page component and navigation item exist, and the backend audit endpoint exists, but the current top-level route dispatch does not appear to map `/coordinator/audit` to that component. Verify and wire this route before considering the coordinator audit screen reachable.
- `GET /health/ready` reports database readiness; `GET /health` is a liveness check.
- Treat the checked-in/local SQLite files as development artifacts, not production data or migration targets.

## 11. Guidance for an AI working on this repository

1. First identify the relevant API route, schema, service, model, frontend screen, and test. Keep changes consistent across all layers that implement the same behavior.
2. Preserve role boundaries, request ownership, donor-match requirements, coordinator verification, and notification privacy. Add or update tests for authorization and state transitions when those are affected.
3. Do not treat frontend-only role checks as sufficient authorization.
4. Keep blood matching explicitly “potential”; do not present match scores or blood-group lookup as medical clearance.
5. Preserve graceful AI-disabled behavior and do not expose provider credentials in browser code.
6. Use Alembic for schema changes and avoid operating migrations on populated development databases without an explicit plan.
7. Run targeted pytest tests for backend changes and `npm run build` for frontend changes; run broader suites when the change crosses those boundaries.
8. Do not commit secrets, real donor/patient personal data, or local database contents.
