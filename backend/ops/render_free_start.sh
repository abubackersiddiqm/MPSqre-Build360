#!/bin/sh
set -eu

PORT="${PORT:-8000}"
export PORT
MAINTENANCE_PID=""

stop_maintenance() {
    if [ -n "${MAINTENANCE_PID:-}" ] && kill -0 "$MAINTENANCE_PID" 2>/dev/null; then
        echo "[R45] Stopping maintenance listener..."
        kill "$MAINTENANCE_PID" 2>/dev/null || true
        wait "$MAINTENANCE_PID" 2>/dev/null || true
    fi
    MAINTENANCE_PID=""
}

cleanup() {
    stop_maintenance
}

trap cleanup EXIT INT TERM

echo "============================================================"
echo "MPSqre Build360 - Render Free Startup R45"
echo "Mode: maintenance-port -> production guard -> migrate -> root verify/bootstrap -> gunicorn"
echo "============================================================"

echo "[R45] Opening temporary maintenance listener on port ${PORT}..."
python ops/render_maintenance_server.py &
MAINTENANCE_PID=$!
sleep 1

if ! kill -0 "$MAINTENANCE_PID" 2>/dev/null; then
    echo "[R45][ERROR] Maintenance listener failed to start on port ${PORT}." >&2
    exit 45
fi

echo "[R45] Validating production environment guard..."
python manage.py build360_environment_status --require production

echo "[R45] Applying pending database migrations..."
python manage.py migrate --noinput

echo "[R45] Verifying ROOT_OPERATOR..."
if python manage.py bootstrap_root_operator --verify-only; then
    echo "[R45] ROOT_OPERATOR already verified. Bootstrap credentials are not required."
else
    echo "[R45] ROOT_OPERATOR not present. Running one-time bootstrap."

    if [ -z "${ROOT_OPERATOR_BOOTSTRAP_EMAIL:-}" ]; then
        echo "[R45][ERROR] ROOT_OPERATOR_BOOTSTRAP_EMAIL is required for first bootstrap." >&2
        exit 41
    fi

    if [ -z "${ROOT_OPERATOR_BOOTSTRAP_PASSWORD:-}" ]; then
        echo "[R45][ERROR] ROOT_OPERATOR_BOOTSTRAP_PASSWORD is required for first bootstrap." >&2
        exit 42
    fi

    ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME="${ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME:-Build360 Root Operator}"
    export ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME

    python manage.py bootstrap_root_operator \
        --email "$ROOT_OPERATOR_BOOTSTRAP_EMAIL" \
        --display-name "$ROOT_OPERATOR_BOOTSTRAP_DISPLAY_NAME" \
        --password-env ROOT_OPERATOR_BOOTSTRAP_PASSWORD

    python manage.py bootstrap_root_operator --verify-only
    echo "[R45] ROOT_OPERATOR bootstrap and verification completed."
fi

echo "[R45] Startup bootstrap completed. Handing port ${PORT} to Gunicorn..."
stop_maintenance
trap - EXIT INT TERM

exec gunicorn \
    --bind="0.0.0.0:${PORT}" \
    --workers=2 \
    --threads=4 \
    --access-logfile=- \
    --error-logfile=- \
    build360.wsgi:application
