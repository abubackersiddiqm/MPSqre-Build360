# Build360 R45 — Render Free Migration Port Guard

## Purpose

Render Free web services must bind a port during deployment. A fresh Build360
production database can require several minutes to apply all Django migrations.
R44 correctly ran the migrations before Gunicorn, but Render could time out its
port scan before migrations completed.

R45 keeps the deployment safe and observable by opening a tiny maintenance
listener on the configured `PORT` before migrations begin.

## Startup sequence

1. Start minimal maintenance listener on `0.0.0.0:$PORT`.
2. Return HTTP 503 only; no repository files or application data are served.
3. Verify `BUILD360_ENVIRONMENT=production`.
4. Run `python manage.py migrate --noinput`.
5. Verify the existing `ROOT_OPERATOR`; bootstrap it only when missing.
6. Stop the maintenance listener.
7. `exec` the normal Gunicorn process on the same port.

Django migration history makes repeated startup safe: already-applied migrations
are skipped and only pending migrations are executed.

## Render Docker Command

Keep this exact command:

    /bin/sh ops/render_free_start.sh

## First ROOT_OPERATOR bootstrap only

The following Render environment variables are required only if no active root
operator exists yet:

- `ROOT_OPERATOR_BOOTSTRAP_EMAIL`
- `ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME`
- `ROOT_OPERATOR_BOOTSTRAP_PASSWORD`

After the logs confirm `ROOT_OPERATOR verified`, remove the three temporary
bootstrap variables from Render. Do not place their values in source control.

## Production frontend origin

For the current Vercel frontend use:

    DJANGO_CSRF_TRUSTED_ORIGINS=https://mpsqre-build360.vercel.app
    DJANGO_CORS_ALLOWED_ORIGINS=https://mpsqre-build360.vercel.app
    BUILD360_PUBLIC_WEB_URL=https://mpsqre-build360.vercel.app

Do not add a trailing slash.

## Files changed by R45

- `backend/ops/render_free_start.sh` — replaces the R44 startup script with a
  port-safe startup sequence.
- `backend/ops/render_maintenance_server.py` — new fixed-response maintenance
  listener; it cannot browse or serve project files.
- `ops/production-r45/RENDER-FREE-MIGRATION-PORT-GUARD.md` — this runbook.

No Django migration, model, seed, `.env`, secret, or database file is added by
this package.
