#!/bin/sh
set -eu

echo "============================================================"
echo "MPSqre Build360 - Render Free Startup R44"
echo "Mode: production guard -> migrate -> root verify/bootstrap -> gunicorn"
echo "============================================================"

python manage.py build360_environment_status --require production

echo "[R44] Applying pending database migrations..."
python manage.py migrate --noinput

echo "[R44] Verifying ROOT_OPERATOR..."
if python manage.py bootstrap_root_operator --verify-only; then
    echo "[R44] ROOT_OPERATOR already verified. Bootstrap credentials are not required."
else
    echo "[R44] ROOT_OPERATOR not present. Running one-time bootstrap."

    if [ -z "${ROOT_OPERATOR_BOOTSTRAP_EMAIL:-}" ]; then
        echo "[R44][ERROR] ROOT_OPERATOR_BOOTSTRAP_EMAIL is required for first bootstrap." >&2
        exit 41
    fi

    if [ -z "${ROOT_OPERATOR_BOOTSTRAP_PASSWORD:-}" ]; then
        echo "[R44][ERROR] ROOT_OPERATOR_BOOTSTRAP_PASSWORD is required for first bootstrap." >&2
        exit 42
    fi

    ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME="${ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME:-Build360 Root Operator}"
    export ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME

    python manage.py bootstrap_root_operator \
        --email "$ROOT_OPERATOR_BOOTSTRAP_EMAIL" \
        --display-name "$ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME" \
        --password-env ROOT_OPERATOR_BOOTSTRAP_PASSWORD

    python manage.py bootstrap_root_operator --verify-only
    echo "[R44] ROOT_OPERATOR bootstrap and verification completed."
fi

echo "[R44] Starting Gunicorn on 0.0.0.0:8000..."
exec gunicorn \
    --bind=0.0.0.0:8000 \
    --workers=2 \
    --threads=4 \
    --access-logfile=- \
    --error-logfile=- \
    build360.wsgi:application
