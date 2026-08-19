from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)

def main() -> None:
    if len(sys.argv) != 2:
        fail("Usage: bootstrap_root_operator.py <project-root>")
    root = Path(sys.argv[1]).resolve()
    env_file = root / "backend" / ".env.production"
    if not env_file.is_file():
        fail("backend/.env.production is missing")
    values = {str(k): str(v) for k, v in dotenv_values(env_file).items() if k and v is not None}
    if values.get("BUILD360_ENVIRONMENT") != "production":
        fail("Production environment file is not configured for production")
    if values.get("BUILD360_DATABASE_NAME_GUARD") != "build360_production":
        fail("Production database guard must be build360_production")

    os.environ.update(values)
    os.environ["BUILD360_ENVIRONMENT"] = "production"
    os.environ["APP_ENV"] = "production"
    os.environ["DJANGO_ENV_FILE"] = "backend\\.env.production"
    sys.path.insert(0, str(root / "backend"))
    os.chdir(root / "backend")

    import django
    django.setup()

    from django.conf import settings
    if settings.BUILD360_ENVIRONMENT != "production":
        fail("Django is not running in production mode")
    if settings.DATABASES["default"]["NAME"] != "build360_production":
        fail("Django is not connected to build360_production")

    from modules.accessops.models import PlatformOperator
    from modules.identity.models import User

    email = input("Production ROOT_OPERATOR email: ").strip().lower()
    name = input("Display name [Build360 Production Administrator]: ").strip() or "Build360 Production Administrator"
    password = getpass.getpass("Password (minimum 14 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        fail("Passwords do not match")
    if len(password) < 14:
        fail("Password must contain at least 14 characters")

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(email=email, password=password, display_name=name)
        action = "created"
    else:
        user.display_name = name
        user.set_password(password)
        user.is_active = True
        user.suspended_at = None
        user.save(update_fields=["display_name", "password", "is_active", "suspended_at", "updated_at"])
        action = "updated"

    operator, _ = PlatformOperator.objects.update_or_create(
        user=user,
        defaults={"operator_type_code": "ROOT_OPERATOR", "is_active": True},
    )
    print(f"[SUCCESS] Production ROOT_OPERATOR {action}: {user.email} / {operator.operator_type_code}")

if __name__ == "__main__":
    main()
