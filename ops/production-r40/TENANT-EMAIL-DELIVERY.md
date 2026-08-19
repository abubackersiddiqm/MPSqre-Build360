# Build360 R40 — Tenant-aware transactional email

Routing policy:

1. White Label disabled -> Build360 platform SMTP.
2. White Label enabled but company SMTP is not ACTIVE -> Build360 platform SMTP.
3. White Label enabled and company SMTP has passed `Test & activate` -> company SMTP.
4. Forgot Password opened on an active tenant domain -> that tenant context is used only when the account has an active membership in that company.
5. Shared Build360 domain + exactly one active white-label membership -> that company context may brand the reset email.
6. Shared Build360 domain + multiple memberships -> platform context; Build360 never guesses a tenant.

Security:

- Company SMTP passwords are encrypted at rest with `TENANT_EMAIL_CREDENTIAL_KEYS`.
- The password is write-only and never returned by the API.
- Company Admin can only manage the currently selected tenant and must have `tenant.branding.manage`.
- SMTP `Test & activate` sends only to the authenticated administrator's own email; there is no arbitrary test-recipient field.
- In production, tenant SMTP is limited to ports 465/587/2525 and hostnames resolving to private/loopback/link-local/reserved addresses are rejected.
- A failed active tenant SMTP route is marked FAILED and the platform transactional sender becomes the fallback.
- Global platform SMTP credentials remain operator-only environment secrets and are never exposed to tenant admins.

Production environment must include a dedicated Fernet key ring:

`TENANT_EMAIL_CREDENTIAL_KEYS=<fernet-key>[,<older-key-for-rotation>]`
