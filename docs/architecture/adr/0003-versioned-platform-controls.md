# ADR-003 — Versioned platform controls before business modules

Status: Accepted

Date: 30 July 2026

## Context

The Product Bible requires statuses, workflows, approvals, company settings,
entitlements, audit evidence, and file handling to remain configurable and
tenant-safe. Implementing CRM or project records before these controls would
force business modules to hardcode behavior or duplicate security boundaries.

## Decision

Build360 will introduce the following shared platform capabilities before its
first business vertical:

1. Global configuration definitions with tenant-owned immutable versions.
2. Tenant-owned workflow definitions with immutable published versions and
   version-pinned in-flight instances.
3. Optimistic concurrency for workflow state changes.
4. Effective-dated subscription plans, subscriptions, and tenant overrides.
5. Private S3-compatible file bytes with governed metadata and scan gating.
6. Append-only audit evidence and transactionally created outbox events.
7. Semantic permissions as the only API authorization input.

Published configuration and workflow versions cannot be edited or deleted.
Posted audit facts cannot be changed. File downloads require tenant context,
permission, active-version status, and a clean scan result.

## Consequences

- Business modules can depend on stable platform contracts instead of embedded
  status and approval logic.
- Configuration/workflow rollback means publishing a new version or selecting a
  previous version; it never rewrites historical versions.
- File provider credentials remain server-side and file bytes remain outside
  PostgreSQL.
- The outbox persistence and retry boundary is ready, but provider-specific
  publishers and operating runbooks remain later work.
- PostgreSQL row-level security remains deferred; application-layer isolation
  and cross-tenant denial tests are mandatory for every tenant-owned model.
