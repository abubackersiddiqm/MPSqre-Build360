# Architecture baseline

## Controlling decisions

- ADR-001: modular monolith before microservices.
- ADR-002: PostgreSQL for transactional metadata; object storage for bytes.
- ADR-003: transactional outbox for reliable business events.
- ADR-008: Redis and Celery for asynchronous work.
- ADR-009: MinIO locally and R2-compatible storage in production.
- ADR-010: extract services only after measured need.

## Layer rule

Each bounded context is organized as `domain`, `application`,
`infrastructure`, `api`, `migrations`, and `tests`. Domain code may not import
Django or another module. Application code coordinates domain behavior and
ports. Infrastructure implements ports. API code translates transport
contracts and never owns business rules.

## Shared kernel

The shared platform is limited to identifiers, tenant context, audit/event
envelopes, correlation, errors, money/quantity primitives, and operational
health. Business entities remain in their owning module.

## Tenancy enforcement

Application-enforced tenant isolation is mandatory and derives company context
from an authenticated active membership. PostgreSQL row-level security is not
enabled in release 0.3.0; every tenant-owned query and command must therefore
use the tenant context and pass cross-tenant denial tests.

