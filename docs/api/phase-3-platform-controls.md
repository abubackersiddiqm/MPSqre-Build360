# Phase 3 platform controls

Release: 0.3.0

Phase 3 adds tenant-owned, permission-gated platform capabilities required before
business modules are introduced. Every endpoint below requires a valid bearer
session and an active membership-derived `X-Company-Id` context.

## Configuration governance

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| GET | `/api/v1/configurations/` | `configuration.read` | List currently effective published versions |
| GET | `/api/v1/configurations/active/{code}` | `configuration.read` | Resolve one effective version |
| POST | `/api/v1/configurations/drafts` | `configuration.manage` | Create a schema-validated draft |
| POST | `/api/v1/configurations/{version_id}/publish` | `configuration.publish` | Publish an immutable version |

Secret configuration payloads are omitted unless the membership also has
`configuration.secret.read`. Publishing records immutable audit evidence and a
transactional outbox event.

## Workflow and approvals

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| POST | `/api/v1/workflows/definitions` | `workflow.manage` | Create a tenant workflow definition |
| POST | `/api/v1/workflows/definitions/{id}/versions` | `workflow.manage` | Create a validated draft version |
| POST | `/api/v1/workflows/versions/{id}/publish` | `workflow.publish` | Publish an immutable workflow version |
| POST | `/api/v1/workflows/definitions/{code}/instances` | `workflow.execute` | Start an instance on the published version |
| POST | `/api/v1/workflows/instances/{id}/transitions` | `workflow.execute` plus transition policy | Execute or request a transition |
| GET | `/api/v1/workflows/approvals` | `workflow.approve` | List pending tenant approvals |
| POST | `/api/v1/workflows/approvals/{id}/decision` | configured approval permission | Approve or reject a task |

Instances use optimistic concurrency through `expected_version`. In-flight
instances retain the workflow version on which they started. Transition and
approval history is append-only.

## Subscription entitlements

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| GET | `/api/v1/subscriptions/effective` | `subscription.read` | Return effective plan entitlements and limits |
| POST | `/api/v1/subscriptions/overrides` | `subscription.manage` | Create an effective-dated tenant override |

Overrides are effective-dated and do not mutate the underlying plan version.
The backend remains the enforcement boundary; frontend capability display is
not authorization.

## Governed private files

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| POST | `/api/v1/files/uploads` | `files.upload` | Initiate a private presigned upload |
| POST | `/api/v1/files/uploads/{version_id}/finalize` | `files.upload` | Verify size/checksum and submit for scanning |
| GET | `/api/v1/files/{file_id}` | `files.read` | Read governed metadata only |
| GET | `/api/v1/files/{file_id}/download` | `files.download` | Issue a short-lived download URL after clean scan |

File bytes remain in private S3-compatible object storage. PostgreSQL stores
metadata, version lineage, checksum, scan state, and access evidence. Downloads
are denied until the active version has passed malware scanning.

## Audit and outbox operations

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| GET | `/api/v1/audit/events` | `audit.read` | Search tenant-scoped append-only audit records |

The outbox supports transactional creation, database-safe claiming, retry
backoff, claim tokens, publication completion, and dead-letter state. Provider
adapters and production dead-letter operations remain later release work.

## Seeded Phase 3 permissions

- `configuration.read`
- `configuration.manage`
- `configuration.publish`
- `configuration.secret.read`
- `workflow.manage`
- `workflow.publish`
- `workflow.execute`
- `workflow.approve`
- `subscription.read`
- `subscription.manage`
- `files.upload`
- `files.read`
- `files.download`
- `audit.read`

Permissions are seeded, not automatically granted. Tenant administrators must
assign them through controlled roles.
