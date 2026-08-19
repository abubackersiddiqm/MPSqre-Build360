# Phase 18 — Cloud Launch and Deployment Operations

## Boundary

Phase 18 adds provider-neutral cloud-target, deployment, backup, restore and secret-rotation
governance. It extends Phase 12 release records without embedding credentials or coupling
business modules directly to a cloud provider.

## API

All routes require an authenticated tenant context and the relevant `cloudops.*` permission.

- `GET /api/v1/cloudops/summary`
- `GET /api/v1/cloudops/portfolio`
- `GET|POST /api/v1/cloudops/targets`
- `POST /api/v1/cloudops/targets/{public_id}/transition`
- `GET|POST /api/v1/cloudops/pipelines`
- `GET|POST /api/v1/cloudops/deployments`
- `POST /api/v1/cloudops/deployments/{public_id}/transition`
- `GET|POST /api/v1/cloudops/backup-policies`
- `GET|POST /api/v1/cloudops/backup-executions`
- `GET|POST /api/v1/cloudops/restore-exercises`
- `POST /api/v1/cloudops/restore-exercises/{public_id}/transition`
- `GET|POST /api/v1/cloudops/secret-policies`
- `POST /api/v1/cloudops/secret-policies/{public_id}/rotate`

## Production controls

- Production targets cannot become active without explicit approval.
- Production deployments require an approved governed release and passing critical checks.
- Deployment approval is separated from the requester.
- Backup evidence uses SHA-256 and private references.
- Restore evidence records measured RPO and RTO and requires independent approval.
- Secret records store references only; raw secret-like values are rejected.
- Local no-Docker mode remains permitted only for local and test environments.

## Delivery assets

- GitHub Actions quality and release-evidence workflows
- Production and staging environment contract examples
- Gunicorn production process configuration
- PostgreSQL backup and restore evidence scripts
- Production smoke-test script
- Environment contract validator
