# NSS BloodConnect Deployment Guide

## Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 15+ for production deployment
- Redis 7+ (or compatible managed Redis) for shared rate limits
- An SMTP relay for password recovery
- A host or platform such as Render, Fly.io, Railway, or a managed container environment
- Access to environment variables for the platform

## Environment variables

Set production values in the hosting platform's secret/configuration manager.
Do not create or commit a production `.env` file. Replace every example hostname
with the exact deployed hostnames before starting the service.

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
# Set JWT_SECRET in the secret manager; use a unique random value of at least 32 characters.
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FRONTEND_URL=https://your-frontend.example.com
BACKEND_URL=https://your-backend.example.com
CORS_ORIGINS=https://your-frontend.example.com
TRUSTED_HOSTS=your-frontend.example.com,your-backend.example.com
RATE_LIMIT_REDIS_URL=rediss://your-managed-redis.example:6379/0
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@example.com
SMTP_STARTTLS=true
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
AUTH_COOKIE_ENABLED=false
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
GEOCODING_PROVIDER=nominatim
GEOCODING_USER_AGENT=NSSBloodConnect/1.0
GEOCODING_TIMEOUT_SECONDS=5.0
AI_ENABLED=false
```

`TRUSTED_HOSTS` is a comma-separated list of exact hostnames without scheme,
path, port, or wildcard. The application rejects missing or wildcard production
host lists. `AI_API_KEY` and other provider credentials should only be set in
the secret manager when the corresponding integration is enabled.

## PostgreSQL

Production deployments should use PostgreSQL rather than SQLite. The application rejects SQLite in production by validation.

Request lifecycle writes use PostgreSQL row locks and database uniqueness/check
constraints. SQLite is supported for local development and tests; its write
serialization guard is process-local and is not a cross-worker concurrency
mechanism. Do not run a multi-worker production deployment on SQLite.

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

Migration `004_request_lifecycle` is forward-only. It adds confirmed-unit and
donation-confirmation records, preserves old fulfilled request statuses while
flagging them as unverified legacy outcomes, and refuses to proceed if existing
match/response rows contain duplicate pairs or orphan references. Test it on a
disposable database first. Do not apply it to a populated database without
explicit approval, a reviewed migration plan, and verified backups. Do not
attempt an automatic downgrade; it would discard confirmation records.

## Hosting options

The repository contains a root `vercel.json` describing frontend/backend
services and rewrites. Verify that file against the selected platform's current
configuration schema before relying on it; this repository has not been
deployed to or validated on Vercel.

The recommended initial architecture is a static CDN for `frontend/` and a
long-running container or managed application service for FastAPI. Run
PostgreSQL and TLS-enabled Redis as managed services on private networking.
Run `python -m app.cli.expire_requests` as a separate scheduled task in the
same trusted network. This keeps API workers out of scheduler ownership and
avoids relying on serverless process lifetime for Redis cleanup or scheduled
work.

If using separate frontend and backend origins, set `VITE_API_BASE_URL` to the
public API URL and set `FRONTEND_URL`/`CORS_ORIGINS` to the exact frontend
origin. Use bearer authentication unless the deployed cookie/CSRF flow has
passed end-to-end tests. Production requires a shared TLS Redis URL and SMTP
sender configuration. If Redis is unavailable, authentication rate-limited
routes fail closed rather than disabling protection.

## Password recovery and privileged accounts

Password reset tokens are single-use, expire after
`PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, and are stored only as hashes. Reset links
carry the token in the URL fragment so it is not sent in HTTP request paths.
SMTP delivery failures are logged without account addresses or token contents;
the request response does not reveal whether an account exists.

Create coordinator or volunteer accounts only from a trusted operations
environment with:

```bash
cd backend
python -m app.cli.provision_user
```

The command prompts for account details and does not echo the password. Public
registration remains limited to requester and donor roles.

## Optional browser cookie sessions

Bearer authentication remains supported. Cookie sessions are additive and
disabled by default. Do not enable them in production until the frontend/API
domains and TLS are deployed and verified. For HTTPS sibling subdomains,
configure matching frontend/backend origins, then set
`AUTH_COOKIE_ENABLED=true`, `AUTH_COOKIE_SECURE=true`,
`AUTH_COOKIE_SAMESITE=lax`, and frontend build variable
`VITE_COOKIE_AUTH_ENABLED=true`. The auth cookie is HttpOnly; unsafe requests
require the CSRF token and an allowed `Origin`. Keep the cookie feature disabled
for production until those checks have passed end-to-end. API clients that
continue to use bearer tokens can send `X-Auth-Mode: bearer` on login; bearer
authorization remains supported during the transition.

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

## Request deadline operations

Open requests expire at their `required_at` deadline. API access enforces
expiration lazily, but production must also schedule this idempotent operation
so requests expire even when nobody visits them:

```bash
cd backend
python -m app.cli.expire_requests
```

Run it from a trusted backend environment using the configured production
database URL, for example every few minutes through the host's scheduler. The
operation writes the expired status, an audit entry, and a requester-scoped
notification in the same transaction. Emergency requests are immediately
flagged for operational escalation; after the deadline the escalation changes
to `emergency_overdue`. These labels do not imply guaranteed donor availability
or provide medical triage.

An accepted donor response is an offer to coordinate, not a donation or
transfusion. Only an authorized coordinator may record a donation outcome.
`units_confirmed` is tracked separately from `units_required`, and a request is
fulfilled only when coordinator-confirmed units equal the requested total.
Requests fulfilled before migration 004 are marked legacy/unverified and must
not be represented as having a verified donation record.

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

1. Configure PostgreSQL, Redis, SMTP, and environment variables.
2. Review the Alembic chain and run it only on the approved target database.
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

## Phase 6 production preparation

### Required backend configuration

Set values in the hosting platform's secret/configuration manager. Do not
commit a production `.env` file.

| Variable | Requirement |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | PostgreSQL URL using the installed psycopg v3 driver: `postgresql+psycopg://<user>:<password>@<host>:5432/<database>` |
| `JWT_SECRET` | Unique high-entropy secret, at least 32 characters; generate per environment and plan rotation/session invalidation |
| `JWT_ALGORITHM` | Keep `HS256`; do not accept algorithms from client input |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Current default is 1440 minutes; explicitly choose an operational session lifetime before public launch |
| `FRONTEND_URL` | Exact HTTPS frontend origin, without path or trailing slash |
| `BACKEND_URL` | Public HTTPS API URL |
| `CORS_ORIGINS` | Comma-separated exact HTTPS origins; include `FRONTEND_URL`; no wildcard |
| `TRUSTED_HOSTS` | Comma-separated exact frontend/API hostnames, without scheme, path, port, or wildcard |
| `RATE_LIMIT_REDIS_URL` | Shared TLS Redis URL (`rediss://`); startup fails if Redis is unavailable |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL` | Approved SMTP relay host, port, and sender; no provider has been selected |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Both empty for an unauthenticated relay or both set through the secret manager |
| `SMTP_STARTTLS` | `true` |
| `AUTH_COOKIE_ENABLED` | Keep `false` until deployed origins, TLS, cookie behavior, and CSRF pass end-to-end tests |
| `AUTH_COOKIE_SECURE` | `true` if cookie authentication is enabled |
| `AUTH_COOKIE_SAMESITE` | Current default is `lax`; evaluate actual frontend/API site topology before changing |

`AI_ENABLED` defaults to `false`. If enabling the assistant, provide
`AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` as appropriate;
provider keys remain backend-only. `VITE_API_BASE_URL` is public frontend build
configuration and must never contain a credential.

The local `.env.example` should use SQLite and omit `JWT_SECRET`, allowing
development to generate a process-local random secret. Tokens consequently do
not survive a backend restart in that mode. Do not copy development defaults
to production.

### Recommended architecture and cost assumptions

Recommended for an initial deployment: static CDN hosting for React; a
long-running container/managed app service for FastAPI; managed PostgreSQL
with private networking and encrypted automated backups; TLS-enabled managed
Redis; an approved SMTP relay; and the request-expiry CLI as a scheduled task
in the same trusted network. Terminate TLS at the platform ingress. Configure
the exact `TRUSTED_HOSTS` value and enforce request-size limits at ingress; the
application does not trust forwarded headers. Do not enable proxy-header
middleware unless the selected host's trusted proxy addresses are known and
restricted.

| Approach | Security and reliability | Operational burden |
| --- | --- | --- |
| Managed application platform plus managed PostgreSQL/Redis | Lower operational risk when private networking, TLS, backups, and health checks are enabled | Lowest maintenance; recurring service costs and provider-specific constraints |
| Container platform plus separately managed data services | Flexible runtime/scaling and managed data durability | Moderate maintenance; configure networking, secrets, deployments, and alerts |
| Self-managed virtual machines and databases | Maximum control, but operator owns patching, failover, backups, TLS, and monitoring | Highest staffing and reliability burden; not recommended for a first public deployment |

Directional planning estimates in USD per month (not live quotes; confirm
current provider pricing, quotas, regional availability, and tax before
selection):

| Option | Small pilot estimate | Free-tier caveats | Main trade-off |
| --- | ---: | --- | --- |
| Static frontend + managed API container + managed PostgreSQL/Redis + SMTP | **$50–200** | Free app tiers may sleep or lack always-on capacity; database tiers may have strict storage/compute limits; Redis quotas and retention may not meet production availability needs | Best balance for this application's persistent API and separate scheduler |
| Single provider platform for app and some data services | **$80–300** | Free credits/tiers are often capped, non-HA, region-limited, or unsuitable for reliable backups; validate each service separately | Easier operations, but greater provider coupling |
| One or more VPS instances with self-managed database/Redis | **$20–80 infrastructure**, excluding operator time and backup storage | Free compute is not a substitute for durable storage, monitoring, patching, and recovery | Lower cash cost, highest reliability/security burden; not recommended for first public release |

Estimates assume one region, low traffic, one API instance, small data tiers,
basic email, modest logs, and no high availability. Backups/PITR, replicas,
larger database storage, observability retention, email volume, and support
plans can materially increase cost. Free tiers may sleep, enforce tight
connection/compute limits, restrict backups, or provide no production SLA;
do not base a blood-donation coordination service on them without verifying
the operational guarantees.

The application is not yet provider-validated. A long-running API service is
preferred over serverless for predictable SQLAlchemy connection pooling and
separate scheduler execution. A serverless deployment would need explicit
validation of connection limits, cold starts, lifespan behavior, Redis client
cleanup, function timeouts, and an external scheduler.

### Request sizes and reverse-proxy trust

There are no upload endpoints in the current backend. Authentication JSON
payloads are limited in application middleware to **16 KiB**; other HTTP
request bodies are limited to **1 MiB**, including chunked bodies. These
conservative limits are above expected login/reset and ordinary JSON
coordination payloads. Reassess them if legitimate large text fields,
attachments, or new integrations are added.

Also configure a request-body cap at ingress (for example, no more than the
application's 1 MiB general limit unless a reviewed endpoint needs a different
cap). The ingress limit protects resources before requests reach the app.
Return a clear 413 response and test both declared `Content-Length` and
streamed/chunked oversized bodies at the selected host.

The API does not trust `X-Forwarded-For`, `Forwarded`, or other forwarded
headers itself. Uvicorn sees the ingress as the client unless proxy-header
support is enabled with a restricted allowlist. Only after selecting a host,
confirming its proxy source addresses, and configuring the ingress to replace
client-supplied forwarding headers, enable Uvicorn's proxy support with
`--proxy-headers --forwarded-allow-ips=<explicit-proxy-IP-or-CIDR-list>`.
Do not use `*` or enable proxy-header trust on a directly reachable backend.
Firewall the backend so only the ingress can connect; otherwise client-IP
rate limits may collapse to one proxy address or be spoofable by a
misconfigured forwarding chain.

### Database release, pooling, backup, and restore

Alembic is the production schema lifecycle mechanism. `Base.metadata.create_all()`
runs only in `APP_ENV=test`. Review migration SQL and exercise it against a new
disposable PostgreSQL database before release. Never migrate a populated
environment without an approved change window and verified backup. Run
migrations as an explicit release step, and do not start the new application
version if migration fails. Readiness currently does not check the Alembic
revision.

The backend currently relies on SQLAlchemy's default non-SQLite pool settings.
Before choosing serverless or multiple replicas, calculate
`(pool_size + max_overflow) × API process count` against the database limit,
then configure and validate pool size, checkout timeout, connection timeout,
pool recycling, and recovery for the selected host. The current production
pool configuration has not been tuned or tested against a hosted PostgreSQL
service and those values are not currently exposed as application environment
settings. Do not copy suggested values into production without load and
failure testing. Record a per-service connection budget: reserve capacity for
migrations, scheduler, monitoring, and operator access; assign each API
process a maximum pool/overflow allowance; multiply by maximum process/replica
count; and keep the sum below the provider's connection limit with an
operational safety margin. Configure driver connection timeout and pool
checkout timeout only after measuring expected concurrency and provider
behavior.

Define an explicit recovery-point objective (RPO), recovery-time objective
(RTO), retention period, encryption/access policy, and backup-failure alert.
Use provider-managed encrypted backups/point-in-time recovery when available.
Otherwise, run a logical backup from an approved secure host:

```powershell
$env:PGPASSFILE = "<protected-passfile-path>"
pg_dump --format=custom --no-owner --file "<protected-backup-path>\bloodconnect.dump" --dbname "host=<db-host> port=5432 dbname=<db-name> user=<backup-role> sslmode=verify-full"
```

Create the passfile through the approved secret-management process and apply
restrictive filesystem permissions. Do not place passwords in connection
strings, command history, or logs. Write backups only to encrypted storage.
Test restoration only to a separate disposable database, never the live
database:

```powershell
pg_restore --clean --if-exists --no-owner --dbname "host=<restore-host> port=5432 dbname=<disposable-db> user=<restore-role> sslmode=verify-full" "<protected-backup-path>\bloodconnect.dump"
```

Restrict backup access, encrypt exports at rest and in transit, and expire them
under the approved retention policy. Verify readiness and representative
workflows after restore. Record backup age, checksum, restore duration, Alembic
revision, verification results, and the resulting RPO/RTO evidence. Confirm
that the restore target is disposable before using `--clean`; never point that
command at a live database. These procedures have not been tested against a
production backup.

Backup verification checklist:

- Confirm the latest successful backup timestamp is within the approved RPO.
- Verify encryption, access controls, retention, and backup-failure alerts.
- Restore to a new isolated disposable PostgreSQL database.
- Check `alembic current`, row counts for selected non-sensitive tables, and
  representative application workflows.
- Record restore duration and compare with the approved RTO.
- Keep the restore evidence; remove only the disposable restore resources
  created for that verification.

### Scheduler, notifications, monitoring, and failure recovery

Run `python -m app.cli.expire_requests` from `backend/` every **2–5 minutes**
with the production database configuration. Use one scheduler instance or an
external singleton scheduler; do not run an uncoordinated copy on every API
worker. PostgreSQL row locks protect concurrent expiry processing, and already
expired requests are excluded from subsequent runs. Verify this behavior on
the chosen PostgreSQL service before public launch. The operation commits each
batch atomically; a failed run should exit nonzero, roll back its transaction,
and be retried by the next scheduled invocation. Alert on command failures,
missed schedules, and growing overdue-request counts. A later successful run
should process work missed during a scheduler outage.

Password-reset email currently uses an in-process background task and has no
durable queue/retry store; a process failure may lose an attempt. The SMTP
send has a finite connection timeout, but there is no retry/backoff or delivery
receipt tracking. Monitor generic delivery failures without logging
addresses, tokens, reset links, or message bodies. Decide whether best-effort
delivery is acceptable or approve a durable queue/retry design. Coordinator
and donor notifications are database records; external delivery is not
configured by the application.

Proposed improvement, not implemented: use a transactional outbox or managed
durable queue with a stable message/deduplication ID, bounded exponential
backoff, maximum-attempt/dead-letter handling, delivery status metrics, and a
manual replay procedure. Password-reset payloads contain bearer-equivalent
secrets, so a queue must encrypt them at rest, restrict worker access, expire
them promptly, and never include them in logs. A database outbox requires an
approved schema change; a managed queue requires a provider/security review.
Do not adopt either design until its secret-retention, deduplication, and
failure semantics are reviewed.

Use centrally collected, access-restricted logs with a defined retention
period. Do not log request bodies, authorization headers, passwords, reset
tokens, patient/donor contact details, or clinical eligibility information.
Monitor liveness, `/health/ready`, API errors/latency, database connections,
Redis availability/latency, scheduler success, SMTP failures, storage, backup
completion, and restore-test age. Assign alert ownership and incident response
before launch. `/health` is liveness; `/health/ready` checks database
connectivity and Redis when configured.

### HTTPS, proxy, and frontend

Serve frontend and API only over HTTPS. API responses include
`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and
`Permissions-Policy`; HSTS is emitted in staging/production and assumes TLS is
correctly terminated before public traffic. In production/staging, the
application requires explicit `TRUSTED_HOSTS` and rejects unlisted `Host`
headers. Development/test keeps a wildcard host setting. The application does
not set a CSP and does not trust forwarded headers. Application request-body
limits are 16 KiB for authentication routes and 1 MiB for other requests;
enforce an additional ingress limit as described above. Configure platform
proxy handling only for documented proxy addresses. Add CSP only after
checking map assets and style/script requirements.

Vite variables are public: `VITE_API_BASE_URL` must contain only the public
API URL. Configure SPA history fallback and verify direct page refreshes.
Bearer auth currently stores tokens in `localStorage`. Cookie authentication
is additive and disabled by default; enabling it needs end-to-end
origin/domain/TLS/CSRF verification.

### Dependency security gate

Phase 6A upgraded compatible dependencies, and Phase 6B replaced
`python-jose` with PyJWT 2.15.1 while preserving the HS256 token contract.
The Phase 6B clean-environment audit reported no known advisories, and
`python-jose`/`ecdsa` were absent from that resolved environment. Re-run
`pip-audit` in the release pipeline; a clean audit is not production security
clearance and does not replace application or infrastructure review.

### Release order, monitoring, and incident response

1. Create/configure hosting, network boundaries, PostgreSQL, Redis, SMTP, and
   the scheduler. Store credentials only in the platform secret manager.
2. Set and validate all production environment variables, including exact
   `TRUSTED_HOSTS`, HTTPS `CORS_ORIGINS`, TLS Redis, and secure SMTP.
3. Build and test the frontend; verify direct page refreshes and the public API
   URL. Do not expose backend credentials through `VITE_*`.
4. Create a verified backup/PITR point, review migration SQL, and run Alembic
   as a separate release step against the explicitly approved database.
5. Start the API only after migrations succeed. Verify `/health`,
   `/health/ready`, allowed/blocked host behavior, TLS, CORS, rate limiting,
   and core workflows.
6. Enable the scheduler once, confirm one expiry cycle and its logs, then
   configure alerts and ownership before opening public access.

At minimum, alert on API 5xx rate/latency, readiness failures, PostgreSQL
connection exhaustion, Redis outage/latency, scheduler nonzero exit or missed
run, SMTP failure rate, backup/PITR failure, storage thresholds, and stale
restore-test age. Use platform logs with access controls and retention limits;
the application does not currently emit a complete structured JSON logging
schema or integrate an error-monitoring SDK. Never add request bodies,
authorization headers, reset tokens, or donor/patient contact details to
monitoring events.

Incident response: restrict public access or disable affected integrations,
preserve access-controlled logs, assess whether account/contact/medical
coordination data may have been exposed, and notify the designated
privacy/security owner. Rotate affected secrets only through the approved
operator process. For failed releases, roll back the application artifact
first; do not automatically downgrade the database. Restore only to a
separate target unless an authorized recovery plan explicitly approves
production restoration.

### Rollback and prerequisites

Keep previous backend and frontend artifacts. Prefer application rollback
without a database downgrade. For a non-backward-compatible migration, pause
release and follow a reviewed forward-repair or restore plan; do not assume an
Alembic downgrade is safe. Confirm backup/PITR and restore testing before the
first live schema change.

Before Phase 7, select a host/domain and service providers; establish secret
ownership/rotation, RPO/RTO, ingress host/body/proxy controls, token lifetime,
scheduler and alerting; decide whether best-effort reset email is acceptable;
clear the backend dependency advisories; and rerun the frontend type-check and
production build in the release pipeline. This preparation did not deploy the
application.
