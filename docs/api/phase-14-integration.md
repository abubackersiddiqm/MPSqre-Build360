# Phase 14 Globalization and Integration API

Base path: `/api/v1/integrations/`

## Endpoints

- `GET summary`
- `GET|POST localization-packs`
- `POST localization-packs/{public_id}/publish`
- `GET|POST exchange-rates`
- `GET|POST connectors`
- `POST connectors/{public_id}/health`
- `POST connectors/{public_id}/status`
- `GET|POST api-clients`
- `POST api-clients/{public_id}/rotate`
- `POST api-clients/{public_id}/revoke`
- `GET|POST webhooks`
- `POST webhooks/{public_id}/simulate`
- `POST webhooks/{public_id}/status`
- `GET|POST mappings`
- `POST mappings/{public_id}/publish`
- `GET|POST sync-runs`
- `POST sync-runs/{public_id}/complete`

All endpoints require an authenticated tenant context and semantic permission. API secrets are returned only during issue or rotation. Raw secrets and webhook payloads are not stored. Exchange-rate records are append-only. Synchronization runs use company-scoped idempotency keys.
