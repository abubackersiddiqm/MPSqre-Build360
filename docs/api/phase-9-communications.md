# Phase 9 communications and notifications API

Phase 9 introduces provider-neutral communications, consent and quiet-hours
policies, versioned templates, signed delivery callbacks, inbound correlation,
and a tenant-scoped notification inbox.

## Tenant API boundaries

Authenticated tenant APIs require the existing bearer token and
`X-Company-Id` membership context.

- `GET /api/v1/communications/summary`
- `GET|PATCH /api/v1/communications/policies`
- `GET|POST /api/v1/communications/providers`
- `GET|POST /api/v1/communications/templates`
- `POST /api/v1/communications/templates/{public_id}/publish`
- `GET|POST /api/v1/communications/consents`
- `GET|POST /api/v1/communications/requests`
- `POST /api/v1/communications/requests/{public_id}/dispatch`
- `POST /api/v1/communications/requests/{public_id}/cancel`
- `GET /api/v1/communications/callbacks`
- `GET /api/v1/communications/inbound`
- `GET /api/v1/notifications/summary`
- `GET|POST /api/v1/notifications/items`
- `POST /api/v1/notifications/items/{public_id}/read`
- `POST /api/v1/notifications/items/read-all`
- `GET|PATCH /api/v1/notifications/preferences`
- `GET|POST /api/v1/notifications/rules`

## Provider callback boundary

`POST /api/v1/communications/provider-callbacks/{provider_public_id}` is
provider-facing and does not use a user session. It requires an HMAC-SHA256
signature in `X-Build360-Signature`. Callback bodies are not retained; the
system stores a SHA-256 payload digest, normalized status evidence, and the
provider event identifier.

## Privacy controls

Communication requests store recipient references rather than raw contact
endpoints. External channel requests are suppressed when the channel is
disabled, consent is not granted, quiet hours apply, daily subject limits are
reached, or a provider/template is unavailable. Provider credentials remain
secret-manager references rather than database values.

The local `local_noop` adapter is restricted to test or explicit local
no-Docker mode. Production provider adapters and regional consent policy packs
require separate validation and configuration.
