# Phase 13 SaaS Control Plane API

Base path: `/api/v1/control-plane/`

The API is authenticated through the normal Build360 JWT but authorizes against effective platform-operator assignments rather than tenant membership roles. Cross-tenant operations are limited to lifecycle, subscription, usage, and support-governance records.

Key resources: `me`, `summary`, `tenants`, `plans`, `subscriptions`, `usage`, `support-requests`, and `operators`. Tenant administrators decide support requests through `/api/v1/companies/current/support-requests/`. Approved records do not mint impersonation or support tokens.
