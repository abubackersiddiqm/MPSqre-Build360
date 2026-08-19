# ADR 0002: Identity, tenancy, and session security

- Status: Accepted for Phase 2
- Date: 2026-07-30
- Product Bible: GOV-001..004, IAM-001..005, CMP-001..004,
  BR-GOV-001, BR-GOV-004..006

## Decision

A person has one platform identity and may hold multiple effective-dated company
memberships. The active company is supplied as `X-Company-Id`, but it becomes
trusted tenant context only after the API validates an active membership for
the authenticated user. Tenant-scoped APIs resolve this context before object
lookup.

Access and refresh credentials are signed JWTs. Access tokens are short-lived.
Every refresh token is represented by a one-way JTI hash in PostgreSQL and is
single-use. Rotation revokes the previous token. Reuse revokes the complete
session token family and creates a security audit event.

Roles are tenant-owned, versioned, effective-dated permission collections.
Permissions are stable semantic codes. API authorization evaluates effective
membership-role grants and never infers permission from a role name.

## Database defense

Phase 2 enforces tenancy in application query/command boundaries and tests.
PostgreSQL row-level security is deferred as defense in depth until connection
pooling and worker tenant-context behavior are approved. This does not weaken
the mandatory application checks.

## Security consequences

Raw refresh tokens and JWTs are never stored. Device sessions can be revoked.
Privileged actions require a recent assurance timestamp; the initial password
login establishes only password assurance. MFA enrollment and challenge
providers remain a subsequent coherent slice under IAM-002/IAM-005.

## Compatibility

No prior application identity or business data exists. This custom user model
must remain the first auth migration and cannot be swapped after production
data is created.

