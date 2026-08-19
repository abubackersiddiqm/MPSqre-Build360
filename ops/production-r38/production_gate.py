from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

REQUIRED = (
    "DJANGO_SECRET_KEY",
    "JWT_SIGNING_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "DATABASE_SSLMODE",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "OBJECT_STORAGE_ENDPOINT",
    "OBJECT_STORAGE_PUBLIC_ENDPOINT",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "OBJECT_STORAGE_BUCKET",
    "CRM_PROTECTED_DATA_KEYS",
    "TENANT_EMAIL_CREDENTIAL_KEYS",
    "CRM_BLIND_INDEX_KEY",
    "BUILD360_PUBLIC_WEB_URL",
    "BUILD360_TRANSACTIONAL_FROM_EMAIL",
    "DJANGO_EMAIL_BACKEND",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
)

PLACEHOLDER_MARKERS = (
    "replace-me",
    "replace-with",
    "example.com",
    "example.net",
    "example.org",
    "changeme",
    "change-me",
    "password",
    "your-domain",
    "your_",
    "<",
    ">",
)

def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)

def load_env(project_root: Path) -> tuple[Path, dict[str, str]]:
    env_file = project_root / "backend" / ".env.production"
    if not env_file.is_file():
        fail(
            f"{env_file} does not exist. Copy backend/.env.production.example "
            "to backend/.env.production and configure production secrets/endpoints."
        )
    values = {
        str(k): str(v)
        for k, v in dotenv_values(env_file).items()
        if k and v is not None
    }
    values["BUILD360_ENVIRONMENT"] = "production"
    values["APP_ENV"] = "production"
    values["DJANGO_ENV_FILE"] = "backend\\.env.production"
    return env_file, values

def reject_placeholders(name: str, value: str) -> None:
    lower = value.lower()
    if any(marker in lower for marker in PLACEHOLDER_MARKERS):
        fail(f"{name} still contains a placeholder/example value")

def csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

def validate_contract(values: dict[str, str]) -> None:
    missing = [name for name in REQUIRED if not values.get(name, "").strip()]
    if missing:
        fail("Missing production variables: " + ", ".join(missing))

    if values.get("BUILD360_ENVIRONMENT") != "production":
        fail("BUILD360_ENVIRONMENT must be production")
    if values.get("APP_ENV") != "production":
        fail("APP_ENV must be production")
    if values.get("LOCAL_NO_DOCKER", "false").strip().lower() in {"1", "true", "yes", "on"}:
        fail("LOCAL_NO_DOCKER must be false in production")

    if values.get("BUILD360_DATABASE_NAME_GUARD") != "build360_production":
        fail("BUILD360_DATABASE_NAME_GUARD must be exactly build360_production")

    for key in REQUIRED:
        reject_placeholders(key, values[key])

    if len(values["DJANGO_SECRET_KEY"]) < 50:
        fail("DJANGO_SECRET_KEY must be at least 50 characters")
    if len(values["JWT_SIGNING_KEY"]) < 50:
        fail("JWT_SIGNING_KEY must be at least 50 characters")
    if values["DJANGO_SECRET_KEY"] == values["JWT_SIGNING_KEY"]:
        fail("DJANGO_SECRET_KEY and JWT_SIGNING_KEY must be different")

    db = urlparse(values["DATABASE_URL"])
    if db.scheme not in {"postgres", "postgresql"}:
        fail("DATABASE_URL must use PostgreSQL")
    if db.path.lstrip("/") != "build360_production":
        fail("DATABASE_URL database name must be build360_production")
    if values["DATABASE_SSLMODE"] not in {"require", "verify-ca", "verify-full"}:
        fail("DATABASE_SSLMODE must require TLS")

    for key in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        parsed = urlparse(values[key])
        if parsed.scheme not in {"rediss", "redis+tls"}:
            fail(f"{key} must use encrypted Redis transport (rediss:// or redis+tls://)")

    for key in ("OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_PUBLIC_ENDPOINT", "BUILD360_PUBLIC_WEB_URL"):
        if urlparse(values[key]).scheme != "https":
            fail(f"{key} must use HTTPS")

    hosts = csv_values(values["DJANGO_ALLOWED_HOSTS"])
    if not hosts or "*" in hosts:
        fail("DJANGO_ALLOWED_HOSTS must contain explicit hosts and cannot use *")
    if any(host in {"localhost", "127.0.0.1"} for host in hosts):
        fail("Production DJANGO_ALLOWED_HOSTS cannot use localhost/127.0.0.1")

    for key in ("DJANGO_CORS_ALLOWED_ORIGINS", "DJANGO_CSRF_TRUSTED_ORIGINS"):
        origins = csv_values(values[key])
        if not origins:
            fail(f"{key} cannot be empty")
        if any(urlparse(origin).scheme != "https" for origin in origins):
            fail(f"{key} must contain HTTPS origins only")

    if values.get("COMMUNICATION_LOCAL_ADAPTER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        fail("COMMUNICATION_LOCAL_ADAPTER_ENABLED must be false in production")
    if values.get("AI_LOCAL_ADAPTER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        fail("AI_LOCAL_ADAPTER_ENABLED must be false in production")
    if values.get("INTEGRATION_LOCAL_SIMULATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
        fail("INTEGRATION_LOCAL_SIMULATION_ENABLED must be false in production")

    email_backend = values.get("DJANGO_EMAIL_BACKEND", "").strip()
    if email_backend != "django.core.mail.backends.smtp.EmailBackend":
        fail("Production transactional identity email must use Django SMTP EmailBackend")

    email_host = values.get("EMAIL_HOST", "").strip().lower()
    if email_host in {"localhost", "127.0.0.1", "::1"}:
        fail("Production EMAIL_HOST cannot use localhost")
    try:
        email_port = int(values.get("EMAIL_PORT", "0"))
    except ValueError:
        fail("EMAIL_PORT must be an integer")
    if not 1 <= email_port <= 65535:
        fail("EMAIL_PORT must be between 1 and 65535")

    use_tls = values.get("EMAIL_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    use_ssl = values.get("EMAIL_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
    if use_tls == use_ssl:
        fail("Production SMTP must enable exactly one of EMAIL_USE_TLS or EMAIL_USE_SSL")

    from_email = values.get("BUILD360_TRANSACTIONAL_FROM_EMAIL", "").strip()
    if "@" not in from_email or from_email.startswith("@") or from_email.endswith("@"):
        fail("BUILD360_TRANSACTIONAL_FROM_EMAIL must be a valid sender email address")

def make_process_env(values: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(values)
    env["BUILD360_ENVIRONMENT"] = "production"
    env["APP_ENV"] = "production"
    env["DJANGO_ENV_FILE"] = "backend\\.env.production"
    return env

def run(project_root: Path, values: dict[str, str], args: list[str]) -> None:
    python = project_root / "backend" / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        fail(f"Backend runtime missing: {python}")
    completed = subprocess.run(
        [str(python), *args],
        cwd=project_root / "backend",
        env=make_process_env(values),
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

def db_fresh_guard(project_root: Path, values: dict[str, str]) -> None:
    python = project_root / "backend" / ".venv" / "Scripts" / "python.exe"
    code = r"""
import os
from urllib.parse import urlparse
import psycopg
u = urlparse(os.environ["DATABASE_URL"])
kwargs = {
    "host": u.hostname,
    "port": u.port or 5432,
    "dbname": u.path.lstrip("/"),
    "user": u.username,
    "password": u.password,
    "sslmode": os.environ["DATABASE_SSLMODE"],
}
with psycopg.connect(**kwargs) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.identity_user'), to_regclass('public.django_migrations')")
        identity_user, django_migrations = cur.fetchone()
        if identity_user is not None:
            raise SystemExit("PRODUCTION DB GUARD: identity_user already exists. R38 initial cutover only migrates a fresh production database.")
        if django_migrations is not None:
            cur.execute("SELECT COUNT(*) FROM django_migrations")
            count = int(cur.fetchone()[0])
            if count:
                raise SystemExit(f"PRODUCTION DB GUARD: django_migrations already contains {count} rows. Review existing production DB before migration.")
print("Production DB freshness guard passed.")
"""
    completed = subprocess.run(
        [str(python), "-c", code],
        cwd=project_root / "backend",
        env=make_process_env(values),
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root")
    parser.add_argument(
        "--mode",
        choices=("validate", "migration-plan", "migrate-fresh"),
        default="validate",
    )
    ns = parser.parse_args()
    project_root = Path(ns.project_root).resolve()

    env_file, values = load_env(project_root)
    validate_contract(values)

    print("============================================================")
    print("Build360 R38 Production Environment Gate")
    print(f"Project     : {project_root}")
    print(f"Env file    : {env_file}")
    print("Environment : PRODUCTION")
    print("DB guard    : build360_production")
    print("============================================================")
    print("[PASS] Production environment contract")

    run(project_root, values, ["manage.py", "build360_environment_status", "--require", "production"])
    run(project_root, values, ["manage.py", "check", "--deploy"])
    run(project_root, values, ["manage.py", "makemigrations", "--check", "--dry-run"])

    if ns.mode in {"migration-plan", "migrate-fresh"}:
        run(project_root, values, ["manage.py", "migrate", "--plan"])

    if ns.mode == "migrate-fresh":
        db_fresh_guard(project_root, values)
        run(project_root, values, ["manage.py", "migrate", "--noinput"])
        run(project_root, values, ["manage.py", "check", "--deploy"])
        print("[PASS] Fresh production database migrated successfully.")

    print("[SUCCESS] Build360 R38 production gate passed.")

if __name__ == "__main__":
    main()
