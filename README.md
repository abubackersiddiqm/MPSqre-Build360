# MPSqre Build360

MPSqre Build360 is an enterprise, multi-tenant Construction Operating System.
This repository implements the Product Bible v0.1 as a secure modular monolith.

## Repository map

- `backend/`: Django/DRF API, domain modules, workers, migrations, and tests.
- `frontend/`: Next.js web application and typed API boundary.
- `infra/`: Nginx and deployment support.
- `docs/`: architecture decisions, governance, and requirement traceability.

## Local start

Build360 supports both containerized deployment and the bundled native Windows
no-Docker development workflow. For the current Windows workflow, use the
versioned release scripts to configure `backend/.env`, start Django from its
virtual environment, and start Next.js from `frontend`. PostgreSQL runs as a
local Windows service.

Docker Compose remains an optional deployment topology, not a prerequisite for
local development.

The API health endpoints are `/api/v1/health/live` and
`/api/v1/health/ready`.

Phase 2 authentication and tenancy contracts are documented in
`docs/api/phase-2-identity-and-tenancy.md`. Phase 3 configuration, workflow,
entitlement, file, audit, and outbox contracts are documented in
`docs/api/phase-3-platform-controls.md`. Phase 9 communication and notification
contracts are documented in `docs/api/phase-9-communications.md`.

## Quality commands

Backend commands run in the API container:

```text
docker compose run --rm api ruff check .
docker compose run --rm api mypy build360 modules
docker compose run --rm api pytest
docker compose run --rm api python manage.py makemigrations --check --dry-run
```

Frontend commands run from `frontend`:

```text
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

## Security

Do not commit secrets or production data. Report vulnerabilities privately
using the process in `SECURITY.md`.

## Phase 10 operational maturity

Build360 now includes governed KPI reports and expiring exports, client/vendor portal access, validation-first imports, privacy request tracking, effective retention policies, and recovery-verification evidence. See `docs/api/phase-10-operations.md`.

## Phase 11 governed AI foundations

Build360 now includes permission-aware grounded summaries, citations, extraction review, advisory risk signals, confirmation-gated tool proposals, and model-policy evaluation evidence. External AI providers are not activated automatically. See `docs/api/phase-11-ai.md`.

## Phase 12 enterprise readiness

Build360 now includes governed runtime environments, release-readiness checks,
SLOs, service-health evidence, incident response, runbooks, feature flags and
maintenance-window approvals. Open the workspace at `/enterprise-admin`. See
`docs/api/phase-12-adminops.md`.


## Phase 13 — SaaS Control Plane

Build360 now includes a platform-operator control plane for tenant lifecycle, published plans, subscription assignment, usage and quota evidence, and approval-governed support access. The control plane is intentionally separate from tenant roles and does not mint impersonation tokens.

## Phase 14 — Globalization and Integration Hub

Phase 14 adds company-scoped regional localization packs, append-only exchange-rate evidence, provider-neutral connector profiles, one-time API client credentials, governed webhooks, versioned data mappings and idempotent synchronization evidence. The native-Windows no-Docker workflow remains supported; external provider calls stay disabled until an approved provider configuration and secret reference are activated.

## Phase 15 — Unified Mobile PWA and Workspace Experience

Phase 15 consolidates the Build360 module portfolio into one permission-aware application shell. It adds responsive desktop navigation, a mobile bottom bar, an authorized workspace launcher, keyboard command palette, recent-workspace memory, notification count integration, account actions, PWA metadata, safe static-asset service-worker caching, and an explicit offline boundary. Authenticated tenant pages and API responses are never cached by the service worker.


## v0.15.2 — Migration, decimal validation and installer compatibility

This maintenance release records the vendor constraint state transition as a governed migration, replaces floating-point DRF decimal thresholds with exact `Decimal` instances, and accepts semantically equivalent Django-generated `vendor.0002` files. The installer rejects unexpected migration operations and normalizes accepted source to the controlled migration copy. It adds no new product capability.

## Phase 16 — Pilot Operations and Go-Live Readiness

Phase 16 converts the completed platform into a governed pilot-launch operating model. It adds company onboarding checklists, master-data validation, training assignments, readiness assessments, adoption snapshots, cutover planning, independent sign-offs and controlled go-live/rollback transitions. Open the workspace at `/pilot-readiness`.

## Phase 17 — Security and Compliance Operations

Phase 17 adds company-scoped readiness frameworks, control assessments, risk governance,
security exceptions, and role-assignment access reviews. Frameworks are evidence tools and
must not be represented as third-party certifications. Open the workspace at `/compliance`.

## Phase 18 — Cloud Launch and Deployment Operations

Phase 18 adds provider-neutral cloud targets, governed promotion pipelines, deployment
execution evidence, encrypted backup policies, restore rehearsals, secret-rotation inventory,
production environment validation, CI quality gates and release-evidence automation. The
native Windows no-Docker workflow remains supported for development, but production requires
managed PostgreSQL, shared cache/broker, private object storage, workers and approved secrets.
Open the workspace at `/cloud-launch`.

## Phase 19 customer success operations

Build360 includes tenant-scoped account health, subscription billing evidence, support SLA governance, adoption snapshots and renewal planning at `/customer-success`.
