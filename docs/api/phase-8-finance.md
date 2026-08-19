# Phase 8 finance API

Base path: `/api/v1/finance`

Endpoints:

- `GET /summary`
- `GET /stages`
- `GET|POST /periods`
- `POST /periods/{public_id}/lock`
- `GET|POST /budgets`
- `POST /budgets/{public_id}/transition`
- `GET|POST /variations`
- `POST /variations/{public_id}/transition`
- `GET|POST /invoices`
- `POST /invoices/{public_id}/transition`
- `GET|POST /payments`
- `POST /payments/{public_id}/transition`
- `GET /ledger`

All routes require authenticated tenant context and semantic finance permissions. Posted commercial facts are append-only and financial periods block new postings after lock.
