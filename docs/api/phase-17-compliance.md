# Phase 17 Security and Compliance API

Base path: `/api/v1/compliance/`

The API is tenant-scoped and requires a valid access token, `X-Company-Id`, an active
membership and semantic permissions.

## Read APIs

- `GET summary` — headline framework, assessment, risk, exception and access-review metrics.
- `GET portfolio` — complete permission-filtered compliance operations portfolio.
- `GET assessments`
- `GET risks`
- `GET exceptions`
- `GET access-reviews`

## Controlled actions

- `POST assessments`
- `POST evaluations/{public_id}/evaluate`
- `POST assessments/{public_id}/transition`
- `POST risks`
- `POST risks/{public_id}/transition`
- `POST exceptions`
- `POST exceptions/{public_id}/decide`
- `POST access-reviews`
- `POST access-review-items/{public_id}/decide`
- `POST access-reviews/{public_id}/transition`

Assessment and access-review approvals enforce independent reviewers. Security exceptions
are time-bound and require documented compensating controls. Risk score is derived from
likelihood multiplied by impact. Material actions append audit and outbox evidence.

The supplied frameworks are readiness templates only and must not be presented as formal
certification or legal compliance advice.
