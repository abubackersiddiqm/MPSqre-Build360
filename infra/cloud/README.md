# Build360 managed-cloud topology

Production must use managed PostgreSQL, a shared Redis-compatible cache and broker,
private S3-compatible object storage, at least one web process, one Celery worker,
and exactly one governed scheduler process. The frontend may be independently hosted,
but all authenticated traffic remains backend-authorized and tenant-scoped.

## Promotion sequence

1. Build immutable frontend and backend artifacts.
2. Produce artifact and migration-plan SHA-256 evidence.
3. Run backend, frontend, security and migration gates.
4. Promote to staging and complete tenant-isolation smoke tests.
5. Verify encrypted backups and an isolated restore rehearsal.
6. Obtain independent production approval in Build360 AdminOps and Cloud Launch.
7. Apply expand-compatible migrations through a one-off migration job.
8. Deploy web, worker and scheduler processes.
9. Run health, authentication, company-selection and critical-workspace smoke tests.
10. Record deployment evidence or execute the governed rollback plan.

Never store production credentials in repository files or workflow definitions.
