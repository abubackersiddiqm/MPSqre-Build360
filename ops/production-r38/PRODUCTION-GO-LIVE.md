# Build360 R38 — Production Cutover Guide

## Production boundary

Do **not** copy the demo database or demo credentials into production.

Build360 production must use:

- HTTPS public domain(s)
- managed PostgreSQL database named `build360_production`
- PostgreSQL TLS (`require`, `verify-ca`, or `verify-full`)
- encrypted Redis/Celery transport (`rediss://` or equivalent)
- private HTTPS object storage
- production SMTP
- separate production secrets
- workers and scheduler
- `LOCAL_NO_DOCKER=false`

## Safe cutover sequence

1. Install R38 tooling with `Apply-Versioned.bat`.
2. Run `Prepare-Production-R38.bat`.
3. Edit `backend/.env.production` with real infrastructure endpoints/secrets.
4. Run `Validate-Production-R38.bat`.
5. Review the migration plan.
6. Run the fresh-production migration command.
7. Bootstrap a **new production ROOT_OPERATOR**.
8. Run the full production build gate.
9. Deploy API, frontend, Celery worker, Celery beat/scheduler, and edge proxy/load balancer.
10. Run production smoke tests against the HTTPS URLs.
11. Only after smoke/UAT approval, point the public DNS/domain.

## Commands

```bat
Prepare-Production-R38.bat "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802"

Validate-Production-R38.bat "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802"

Migrate-Production-R38.bat "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802" APPLY_FRESH_PRODUCTION_MIGRATIONS

Bootstrap-Production-Root-R38.bat "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802"

Build-Production-R38.bat "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802"

Smoke-Production-R38.ps1 "D:\MPSqre\MPSqre_Build360_PRODUCTION_SOURCE_20260818_103802" "https://api.YOURDOMAIN.com/api/v1" "https://YOURDOMAIN.com"
```

## Critical notes

- `Migrate-Production-R38.bat` intentionally refuses a database that already contains Build360 `identity_user` data or applied Django migrations. R38 is the **initial clean production cutover** path.
- Never run `seed_build360_demo` in production. The app already blocks this outside `BUILD360_ENVIRONMENT=demo`.
- Never reuse the demo ROOT_OPERATOR password.
- Production infrastructure credentials must not be committed to Git.
