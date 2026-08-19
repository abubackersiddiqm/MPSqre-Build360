# Build360 R44 — Render Free Startup Bootstrap

## Purpose

Render Free web services do not provide Shell/SSH or Pre-Deploy Commands. R44 provides a controlled startup wrapper for the free-tier preview/cutover environment.

Startup order:

1. Verify `BUILD360_ENVIRONMENT=production` and the production database guard.
2. Run `python manage.py migrate --noinput`.
3. Verify the single active `ROOT_OPERATOR`.
4. If no root exists, bootstrap it from temporary environment variables.
5. Re-verify the root invariant.
6. Start Gunicorn.

No demo/company/member seed data is created.

## Render Docker Command

After this patch is committed and pushed to GitHub, set the Render Docker Command to:

```text
/bin/sh ops/render_free_start.sh
```

## One-time bootstrap variables

Only for the first ROOT_OPERATOR bootstrap:

```text
ROOT_OPERATOR_BOOTSTRAP_EMAIL=<root email>
ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME=Build360 Root Operator
ROOT_OPERATOR_BOOTSTRAP_PASSWORD=<new strong password, minimum 14 chars>
```

The password is read from the environment by name; it is not passed as a command-line value.

After the logs confirm `ROOT_OPERATOR verified`, delete `ROOT_OPERATOR_BOOTSTRAP_PASSWORD`. The email/display-name variables may also be deleted. Future starts verify the existing root and do not require bootstrap credentials.

## Free-tier limitation

R44 intentionally runs migrations at web-service startup because Render Free has no Pre-Deploy Command. Before upgrading to a paid production service, move migrations back to Render Pre-Deploy and clear the Docker Command so the image's normal Gunicorn CMD is used.

## Gunicorn permission repair

R44 also creates `/app/.gunicorn` owned by the non-root `build360` runtime user, removing the Gunicorn 26 control-server permission warning without running the application as root.
