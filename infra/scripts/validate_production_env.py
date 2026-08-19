from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


REQUIRED = [
    "DJANGO_SECRET_KEY",
    "JWT_SIGNING_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "OBJECT_STORAGE_ENDPOINT",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "OBJECT_STORAGE_BUCKET",
    "CRM_PROTECTED_DATA_KEYS",
    "CRM_BLIND_INDEX_KEY",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env not in {"staging", "production"}:
        fail("APP_ENV must be staging or production")
    missing = [name for name in REQUIRED if not os.getenv(name)]
    if missing:
        fail("Missing required variables: " + ", ".join(missing))
    if os.getenv("LOCAL_NO_DOCKER", "false").lower() in {"1", "true", "yes", "on"}:
        fail("LOCAL_NO_DOCKER is prohibited for staging and production")
    if len(os.environ["DJANGO_SECRET_KEY"]) < 50:
        fail("DJANGO_SECRET_KEY must contain at least 50 characters")
    if len(os.environ["JWT_SIGNING_KEY"]) < 50:
        fail("JWT_SIGNING_KEY must contain at least 50 characters")
    if os.environ["DJANGO_SECRET_KEY"] == os.environ["JWT_SIGNING_KEY"]:
        fail("Django and JWT signing keys must be distinct")
    if os.getenv("DATABASE_SSLMODE") not in {"require", "verify-ca", "verify-full"}:
        fail("DATABASE_SSLMODE must require TLS")
    if urlparse(os.environ["OBJECT_STORAGE_ENDPOINT"]).scheme != "https":
        fail("OBJECT_STORAGE_ENDPOINT must use HTTPS")
    for name in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        if urlparse(os.environ[name]).scheme not in {"rediss", "redis+tls"}:
            fail(f"{name} must use encrypted transport")
    hosts = {value.strip() for value in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")}
    if not hosts or "*" in hosts:
        fail("DJANGO_ALLOWED_HOSTS must be explicit")
    if not os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS"):
        fail("DJANGO_CSRF_TRUSTED_ORIGINS is required")
    print(f"Build360 {app_env} environment contract is valid.")


if __name__ == "__main__":
    main()
