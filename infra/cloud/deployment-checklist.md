# Production launch checklist

- [ ] Production runtime environment has an approved region and data-residency decision.
- [ ] Managed PostgreSQL enforces TLS, backups, PITR and restricted network access.
- [ ] Redis-compatible cache and Celery broker use encrypted transport.
- [ ] Object storage is private and signed access is enforced.
- [ ] Web, worker and scheduler processes use distinct service identities.
- [ ] Secrets are injected from a managed vault and rotation owners are assigned.
- [ ] Database migrations are reviewed and have a rollback or forward-fix strategy.
- [ ] Staging tenant-isolation, authentication and authorization smoke tests passed.
- [ ] Backup integrity and restore rehearsal evidence is approved.
- [ ] Release artifact, migration plan and logs have SHA-256 evidence.
- [ ] Monitoring, alerts, incident ownership and runbooks are active.
- [ ] Production approval is independent from the release requester.
