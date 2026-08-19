# Phase 19 Customer Success and Billing API

Tenant base path: `/api/v1/customer-success/`

## Read models

- `GET summary`
- `GET portfolio`
- `GET tickets`
- `GET invoices`
- `GET payments`
- `GET plans`
- `GET adoption-snapshots`

## Commands

- `POST tickets`
- `POST tickets/{public_id}/transition`
- `POST invoices`
- `POST invoices/{public_id}/issue`
- `POST payments`
- `POST plans`
- `POST adoption-snapshots`

All endpoints require an authenticated tenant context and semantic `success.*` permissions. Invoice and payment values use fixed-precision decimals. Support deadlines derive from active severity-specific SLA policies. Material commands append audit and transactional outbox evidence.
