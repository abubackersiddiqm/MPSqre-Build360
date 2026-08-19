from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security)
def cloud_launch_security_checks(app_configs, **kwargs):
    del app_configs, kwargs
    issues = []
    environment = str(
        getattr(settings, "BUILD360_ENVIRONMENT", "")
    ).strip().lower()

    # Build360 v1.0.0 has four first-class environments. Development and
    # testing are always non-production. Demo may run in two modes:
    # - LOCAL_NO_DOCKER=True: local/demo workstation runtime, so production
    #   infrastructure checks must not block management commands.
    # - LOCAL_NO_DOCKER=False: hosted demo, which must keep production-grade
    #   HTTPS and PostgreSQL TLS checks.
    if environment:
        if environment in {"development", "testing"}:
            return issues
        if environment == "demo" and settings.LOCAL_NO_DOCKER:
            return issues
    elif settings.APP_ENV in {"local", "test"}:
        # Backward-compatible fallback for pre-v1.0.0 settings.
        return issues
    if settings.LOCAL_NO_DOCKER:
        issues.append(
            Error(
                "LOCAL_NO_DOCKER cannot be used outside local or test environments.",
                id="cloudops.E001",
            )
        )
    if "*" in settings.ALLOWED_HOSTS:
        issues.append(
            Error(
                "Production ALLOWED_HOSTS cannot contain a wildcard.",
                id="cloudops.E002",
            )
        )
    if not settings.CSRF_TRUSTED_ORIGINS:
        issues.append(
            Error(
                "Production CSRF trusted origins must be configured.",
                id="cloudops.E003",
            )
        )
    if not settings.CORS_ALLOWED_ORIGINS:
        issues.append(
            Warning(
                "No production CORS origins are configured.",
                id="cloudops.W001",
            )
        )
    storage_scheme = urlparse(settings.OBJECT_STORAGE_ENDPOINT).scheme
    if storage_scheme != "https":
        issues.append(
            Error(
                "Production object-storage endpoints must use HTTPS.",
                id="cloudops.E004",
            )
        )
    sslmode = str(settings.DATABASES["default"].get("OPTIONS", {}).get("sslmode", ""))
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        issues.append(
            Error(
                "Production PostgreSQL must require TLS.",
                hint="Set DATABASE_SSLMODE=require or verify-full.",
                id="cloudops.E005",
            )
        )
    return issues
