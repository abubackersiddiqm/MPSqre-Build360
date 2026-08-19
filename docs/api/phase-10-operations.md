# Phase 10 reports, portals and operational maturity API

Phase 10 adds tenant-scoped reporting, governed external access, validation-first imports, privacy workflows, retention policies and recovery-verification evidence.

## Reporting

- `GET /api/v1/reporting/summary`
- `GET|POST /api/v1/reporting/metrics`
- `GET|POST /api/v1/reporting/saved`
- `GET|POST /api/v1/reporting/runs`
- `GET /api/v1/reporting/runs/{run_public_id}/download`

Report exports are generated from an immutable metric snapshot, integrity checked with SHA-256, classified, audited, and time limited. CSV, XLSX and PDF are supported without storing report bytes in PostgreSQL.

## Portals

- `GET /api/v1/portal/summary`
- `GET|POST /api/v1/portal/invitations`
- `POST /api/v1/portal/invitations/accept`
- `GET|POST /api/v1/portal/grants`
- `POST /api/v1/portal/grants/{grant_public_id}/revoke`
- `GET|POST /api/v1/portal/shares`
- `GET /api/v1/portal/me`

Invitation tokens are stored only as digests. Acceptance requires an authenticated user whose email matches the invitation. Portal permissions are allow-listed by portal type, and record shares are validated against tenant and project/customer/vendor scope.

## Data operations and privacy

- `GET /api/v1/dataops/summary`
- `GET|POST /api/v1/dataops/templates`
- `GET|POST /api/v1/dataops/imports`
- `POST /api/v1/dataops/imports/{job_public_id}/commit`
- `GET|POST /api/v1/dataops/privacy`
- `POST /api/v1/dataops/privacy/{request_public_id}/resolve`
- `GET|POST /api/v1/dataops/retention`
- `GET|POST /api/v1/dataops/recovery`
- `POST /api/v1/dataops/recovery/{verification_public_id}/complete`

Imports are staged and validated before domain services create records. Retention and recovery records provide governance evidence; they do not substitute for production backup infrastructure or jurisdiction-specific privacy review.
