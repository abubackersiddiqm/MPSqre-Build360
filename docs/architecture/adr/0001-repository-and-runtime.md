# ADR 0001: Repository and runtime baseline

- Status: Accepted for Phase 0-1
- Date: 2026-07-29
- Product Bible: ADR-001, ADR-002, ADR-003, ADR-008, ADR-009, ADR-010

## Decision

Use a monorepo with a Django 6 modular-monolith backend, Next.js 16 frontend,
PostgreSQL, Redis/Celery, MinIO-compatible local object storage, Nginx, and
Docker Compose. Use Python 3.14 and Node.js 24 LTS.

Dependencies are locked by exact application manifests and immutable container
tags/digests should be recorded by the release pipeline before production.

## Consequences

Module boundaries must be enforced with tests. External calls happen after
commit through workers. This phase does not create tenant business models,
authentication, authorization, workflow, or file-upload behavior.

