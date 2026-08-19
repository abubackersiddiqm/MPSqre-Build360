# Phase 2 identity and tenancy contracts

Controlling requirements: GOV-001..004, IAM-001..005, CMP-001..004,
EMP-001..002, BR-GOV-001, BR-GOV-004..006.

## Authentication endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/token` | Password authentication and device session creation |
| POST | `/api/v1/auth/refresh` | Single-use refresh-token rotation |
| POST | `/api/v1/auth/logout` | Revoke the current device session |
| GET | `/api/v1/auth/me` | Identity and active company memberships |
| GET | `/api/v1/auth/sessions` | Bounded device-session inventory |
| POST | `/api/v1/auth/sessions/{id}/revoke` | Revoke a user-owned session |

Access credentials use the `Authorization: Bearer` header. Refresh credentials
are accepted only by the refresh command. Browser clients use the Next.js
server boundary, which stores both credentials in HttpOnly, SameSite cookies;
browser JavaScript receives neither raw credential.

## Tenant context

Tenant-scoped requests provide `X-Company-Id`. The value is an untrusted
selector. `TenantScopedAPIView` resolves an active user, active session, active
company, and effective unsuspended membership before any object lookup.
Failures are concealed as `404` where a cross-tenant identifier could reveal
existence.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/companies/current` | Current authorized company |
| GET | `/api/v1/companies/current/capabilities` | Effective semantic permission codes |

UI action visibility must use returned permission codes, but every mutation
must independently call the backend permission policy.

## Session security

- Access lifetime: maximum 15 minutes.
- Refresh lifetime: environment configured, 30-day default.
- Refresh JTI values are stored only as SHA-256 hashes.
- Refresh rotation is transactional and single-use.
- Reuse revokes the complete device session and token family.
- Suspension and termination revoke active sessions without deleting identity
  or historical ownership.
- Argon2 is the primary password hasher.
- MFA challenge/enrollment and external SSO/SCIM adapters remain explicitly
  deferred; privileged policies can already require recent assurance.

## Audit and events

Session, reuse, lifecycle, and role-assignment commands create append-only
audit evidence and outbox events in the same database transaction. PostgreSQL
adds a trigger preventing update or delete of audit rows.

No raw credential, password, protected contact value, or full request payload
is stored in audit or event records.

