# Phase 12 — Enterprise Administration and Reliability

Phase 12 provides tenant-scoped production-readiness governance without weakening the existing no-Docker Windows development workflow.

## API boundary

All routes are under `/api/v1/adminops/` and require an authenticated tenant context.

- `GET /summary`
- `GET|POST /environments`
- `GET|POST /releases`
- `POST /releases/{public_id}/transition`
- `GET|POST /checks`
- `GET|POST /objectives`
- `GET|POST /health`
- `GET|POST /incidents`
- `POST /incidents/{public_id}/transition`
- `GET|POST /runbooks`
- `GET|POST /flags`
- `PATCH /flags/{public_id}`
- `GET|POST /maintenance`
- `POST /maintenance/{public_id}/transition`

## Release governance

A release is bound to one company and one runtime environment. Validation and approval are blocked until every critical readiness check has passed or has an explicitly authorized waiver. Approval is maker-checker controlled: the release requester cannot approve the same release.

## Reliability evidence

Service objectives and health snapshots preserve measured operational evidence. Health snapshots are append-oriented observations; they do not mutate the authoritative business modules.

## Incident governance

Incidents follow a controlled lifecycle from identification through closure. Incidents requiring a postmortem cannot be closed without a postmortem reference. All material transitions create audit and outbox evidence.

## Feature and maintenance controls

Approval-controlled feature flags require an independent approver before enablement. Maintenance windows are environment-scoped and use an independent approval rule.

## Local mode

Phase 12 does not require Docker. Native Windows development continues to use local PostgreSQL, Django venv, Next.js, local-memory cache, and eager task execution.
