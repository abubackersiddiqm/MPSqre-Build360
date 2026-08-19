# MPSqre Build360 — Production Cutover Guide R43

## Final product behavior

Customer-facing pages do not display environment names such as DEMO, TESTING or
PRODUCTION. Environment separation remains an internal security control.

Password reset:
- Always returns a generic browser message.
- Production/testing never expose reset UID/token/link in browser/API.
- Reset instructions are delivered by governed transactional email.

Company/user invitation:
- Production/testing never expose activation token/link in the create/resend API.
- Activation is delivered through email.
- Development/demo may retain inline link material for controlled local use.
- Resend revokes the old pending token and sends a fresh invitation.

Access:
- ROOT_OPERATOR creates companies and assigns packages.
- Package + standard role + active membership determines effective tenant access.
- Company Administrators create users; raw per-user permission assignment is not
  required for the standard onboarding flow.

## Render production sequence

1. Create a dedicated Render PostgreSQL database named `build360_production`.
2. Create the Django backend service and connect it to the PostgreSQL internal URL.
3. Configure production secrets/environment variables in Render.
4. Deploy backend.
5. Run migrations once against the production database.
6. Run `python manage.py bootstrap_root_operator` once.
7. Deploy frontend with the production backend URL.
8. Sign in as ROOT_OPERATOR, create the first company, choose its package and send
   the first Company Administrator invitation.
9. Company Administrator accepts the email invitation and creates company users.
10. Verify Forgot Password, invitation delivery, CRM package visibility, file
    storage, backup/restore, health checks and logs before customer launch.

## Core backend environment

BUILD360_ENVIRONMENT=production
APP_ENV=production
BUILD360_DATABASE_NAME_GUARD=build360_production
DATABASE_URL=<Render PostgreSQL internal URL>
LOCAL_NO_DOCKER=false

DJANGO_SECRET_KEY=<strong unique 50+ character secret>
JWT_SIGNING_KEY=<different strong unique 50+ character secret>
DJANGO_ALLOWED_HOSTS=<backend hostname>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<frontend-domain>
DJANGO_CORS_ALLOWED_ORIGINS=https://<frontend-domain>
BUILD360_PUBLIC_WEB_URL=https://<frontend-domain>

## Platform Zoho email

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.zoho.in
EMAIL_PORT=587
EMAIL_HOST_USER=admin@tncna.co
EMAIL_HOST_PASSWORD=<Zoho app password>
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_TIMEOUT=20
BUILD360_TRANSACTIONAL_FROM_EMAIL=admin@tncna.co
BUILD360_SUPPORT_EMAIL=admin@tncna.co

R43 automatically maps Django DEFAULT_FROM_EMAIL and SERVER_EMAIL to
BUILD360_TRANSACTIONAL_FROM_EMAIL.

## Required production crypto/infrastructure

Keep separate strong values for:
- CRM_PROTECTED_DATA_KEYS
- CRM_BLIND_INDEX_KEY
- TENANT_EMAIL_CREDENTIAL_KEYS
- COMMUNICATION_CALLBACK_KEYS_JSON

Production also requires the existing Build360 object-storage, Redis/cache,
database TLS, allowed-host, CORS/CSRF and cloud readiness controls to pass.

Do not copy DEMO or TESTING database data into production.
Do not run demo/testing seed commands in production.
Do not create Company Administrators with the retired local bootstrap script.
