import json
import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from build360.environment import load_project_environment, normalize_environment

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = load_project_environment(BASE_DIR)

BUILD360_ENVIRONMENT = normalize_environment(
    os.getenv("BUILD360_ENVIRONMENT") or os.getenv("APP_ENV") or "development"
)
APP_VERSION = (os.getenv("APP_VERSION") or "1.0.0").strip()
if not APP_VERSION:
    raise ImproperlyConfigured("APP_VERSION cannot be blank")

LEGACY_APP_ENV_BY_ENVIRONMENT = {
    "development": "local",
    "testing": "test",
    "demo": "demo",
    "production": "production",
}
APP_ENV = LEGACY_APP_ENV_BY_ENVIRONMENT[BUILD360_ENVIRONMENT]
configured_legacy_app_env = os.getenv("APP_ENV", "").strip().lower()
if configured_legacy_app_env and normalize_environment(configured_legacy_app_env) != BUILD360_ENVIRONMENT:
    raise ImproperlyConfigured(
        "APP_ENV and BUILD360_ENVIRONMENT point to different environments"
    )
os.environ["BUILD360_ENVIRONMENT"] = BUILD360_ENVIRONMENT
os.environ["APP_ENV"] = APP_ENV
os.environ["APP_VERSION"] = APP_VERSION

DEBUG = BUILD360_ENVIRONMENT == "development"
LOCAL_NO_DOCKER = os.getenv("LOCAL_NO_DOCKER", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
if LOCAL_NO_DOCKER and BUILD360_ENVIRONMENT not in {"development", "testing", "demo"}:
    raise ImproperlyConfigured(
        "LOCAL_NO_DOCKER is restricted to development, testing and demo environments"
    )


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is missing")
    return value


def csv(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


SECRET_KEY = required("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters")

ALLOWED_HOSTS = csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = csv("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = csv("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    "modules.identity",
    "modules.tenant",
    "modules.employee",
    "modules.configuration",
    "modules.workflow",
    "modules.subscription",
    "modules.files",
    "modules.crm",
    "modules.projects",
    "modules.design",
    "modules.estimation",
    "modules.vendor",
    "modules.inventory",
    "modules.procurement",
    "modules.fieldops",
    "modules.labour",
    "modules.equipment",
    "modules.quality",
    "modules.safety",
    "modules.finance",
    "modules.communication",
    "modules.notifications",
    "modules.reporting",
    "modules.portal",
    "modules.dataops",
    "modules.ai",
    "modules.adminops",
    "modules.controlplane",
    "modules.integration",
    "modules.pilotops",
    "modules.compliance",
    "modules.cloudops",
    "modules.successops",
    "modules.peopleops",
    "modules.platform",







    "modules.accessops",
    "modules.orgops",
    "modules.workops",
    "modules.myworkops",
    "modules.collabops",
    "modules.releaseops",
    "modules.stabilityops",
    "modules.goliveops",
    "modules.supportops",
    "modules.insightops",
    "modules.sustainabilityops",
    "modules.digitaltwinops",
    "modules.facilityops",
    "modules.leaseops",
    "modules.salesops",
    "modules.landops",
    "modules.capitalops",
    "modules.risktransferops",
    "modules.commercialops",
    "modules.documentops",
    "modules.qualityops",
    "modules.safetyops",
    "modules.equipmentops",
    "modules.workforceops",
    "modules.payrollops",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "modules.platform.middleware.CorrelationIdMiddleware",
    "modules.stabilityops.middleware.RequestTimingMiddleware",
]

ROOT_URLCONF = "build360.urls"
WSGI_APPLICATION = "build360.wsgi.application"
ASGI_APPLICATION = "build360.asgi.application"

database_url = urlparse(required("DATABASE_URL"))
DATABASES: dict[str, dict[str, object]]
if BUILD360_ENVIRONMENT == "testing" and database_url.scheme == "sqlite":
    sqlite_name = (
        ":memory:"
        if database_url.path in {"/:memory:", ":memory:"}
        else database_url.path
    )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name or ":memory:",
        }
    }
else:
    if database_url.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": database_url.path.lstrip("/"),
            "USER": database_url.username,
            "PASSWORD": database_url.password,
            "HOST": database_url.hostname,
            "PORT": database_url.port or 5432,
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"sslmode": os.getenv("DATABASE_SSLMODE", "prefer")},
        }
    }

    database_name = str(DATABASES["default"]["NAME"])
    database_guard = os.getenv("BUILD360_DATABASE_NAME_GUARD", "").strip()
    if BUILD360_ENVIRONMENT in {"demo", "production"} and not database_guard:
        raise ImproperlyConfigured(
            "BUILD360_DATABASE_NAME_GUARD is required for demo and production"
        )
    if database_guard and database_name != database_guard:
        raise ImproperlyConfigured(
            "DATABASE_URL points to a database that does not match "
            f"BUILD360_DATABASE_NAME_GUARD ({database_guard})"
        )

    if BUILD360_ENVIRONMENT == "testing":
        # The local testing database is intentionally owned by the least-
        # privileged Build360 application role. That role must NOT receive
        # PostgreSQL CREATEDB just to satisfy Django's default test_<name>
        # behavior. The governed backend test runner uses --reuse-db and
        # directs Django's TEST database to the already-provisioned
        # build360_testing database.
        test_database_name = os.getenv(
            "BUILD360_TEST_DATABASE_NAME",
            database_name,
        ).strip()
        if not test_database_name:
            raise ImproperlyConfigured(
                "BUILD360_TEST_DATABASE_NAME cannot be blank in testing"
            )
        if test_database_name != database_name:
            raise ImproperlyConfigured(
                "BUILD360_TEST_DATABASE_NAME must match the active testing "
                "DATABASE_URL database"
            )
        DATABASES["default"]["TEST"] = {"NAME": test_database_name}

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "modules.identity.api.authentication.JwtAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "modules.platform.api.errors.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "modules.platform.api.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/minute",
        "refresh": "30/minute",
        "password_reset": "5/minute",
        "crm_contact_reveal": os.getenv("CRM_CONTACT_REVEAL_THROTTLE_RATE", "30/minute"),
    },
}

AUTH_USER_MODEL = "identity.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

JWT_SIGNING_KEY = required("JWT_SIGNING_KEY")
if len(JWT_SIGNING_KEY) < 50:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must contain at least 50 characters")
if JWT_SIGNING_KEY == SECRET_KEY:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be distinct from DJANGO_SECRET_KEY")
JWT_ISSUER = os.getenv("JWT_ISSUER", "mpsqre-build360")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "mpsqre-build360-api")
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "900"))
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "2592000"))
JWT_STEP_UP_TTL_SECONDS = int(os.getenv("JWT_STEP_UP_TTL_SECONDS", "300"))
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))
if PASSWORD_RESET_TIMEOUT < 300 or PASSWORD_RESET_TIMEOUT > 86400:
    raise ImproperlyConfigured("PASSWORD_RESET_TIMEOUT must be between 300 and 86400 seconds")
if JWT_ACCESS_TTL_SECONDS > 900:
    raise ImproperlyConfigured("JWT access-token lifetime cannot exceed 15 minutes")



CRM_PROTECTED_DATA_KEYS = csv("CRM_PROTECTED_DATA_KEYS")
CRM_BLIND_INDEX_KEY = os.getenv("CRM_BLIND_INDEX_KEY", "")
if BUILD360_ENVIRONMENT == "testing":
    if not CRM_PROTECTED_DATA_KEYS:
        CRM_PROTECTED_DATA_KEYS = [
            "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
        ]
    if not CRM_BLIND_INDEX_KEY:
        CRM_BLIND_INDEX_KEY = "build360-test-blind-index-key-only"
elif not CRM_PROTECTED_DATA_KEYS or not CRM_BLIND_INDEX_KEY:
    raise ImproperlyConfigured(
        "CRM_PROTECTED_DATA_KEYS and CRM_BLIND_INDEX_KEY are required"
    )

TENANT_EMAIL_CREDENTIAL_KEYS = csv("TENANT_EMAIL_CREDENTIAL_KEYS")
if BUILD360_ENVIRONMENT == "testing" and not TENANT_EMAIL_CREDENTIAL_KEYS:
    TENANT_EMAIL_CREDENTIAL_KEYS = list(CRM_PROTECTED_DATA_KEYS)
elif BUILD360_ENVIRONMENT in {"development", "demo"} and not TENANT_EMAIL_CREDENTIAL_KEYS:
    TENANT_EMAIL_CREDENTIAL_KEYS = list(CRM_PROTECTED_DATA_KEYS)
elif BUILD360_ENVIRONMENT == "production" and not TENANT_EMAIL_CREDENTIAL_KEYS:
    raise ImproperlyConfigured("TENANT_EMAIL_CREDENTIAL_KEYS is required in production")

try:
    COMMUNICATION_CALLBACK_KEYS = json.loads(
        os.getenv("COMMUNICATION_CALLBACK_KEYS_JSON", "{}")
    )
except json.JSONDecodeError as exc:
    raise ImproperlyConfigured(
        "COMMUNICATION_CALLBACK_KEYS_JSON must be a JSON object"
    ) from exc
if not isinstance(COMMUNICATION_CALLBACK_KEYS, dict):
    raise ImproperlyConfigured(
        "COMMUNICATION_CALLBACK_KEYS_JSON must contain a JSON object"
    )
if BUILD360_ENVIRONMENT == "testing" and not COMMUNICATION_CALLBACK_KEYS:
    COMMUNICATION_CALLBACK_KEYS = {"test": "build360-test-callback-secret"}
if LOCAL_NO_DOCKER and not COMMUNICATION_CALLBACK_KEYS:
    COMMUNICATION_CALLBACK_KEYS = {
        "local": "build360-local-callback-secret-not-for-production"
    }
COMMUNICATION_LOCAL_ADAPTER_ENABLED = (
    BUILD360_ENVIRONMENT in {"testing", "demo"}
    or LOCAL_NO_DOCKER
    or os.getenv("COMMUNICATION_LOCAL_ADAPTER_ENABLED", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)

# Transactional identity/access email uses Build360 platform SMTP by default.
# White-label tenants may opt into a separately verified tenant SMTP route; platform
# SMTP remains the controlled fallback and its credentials are never exposed to tenants.
BUILD360_PUBLIC_WEB_URL = os.getenv("BUILD360_PUBLIC_WEB_URL", "http://localhost:3000").strip().rstrip("/")
BUILD360_TRANSACTIONAL_FROM_EMAIL = os.getenv("BUILD360_TRANSACTIONAL_FROM_EMAIL", "notifications@mpsqre.com").strip()
BUILD360_SUPPORT_EMAIL = os.getenv("BUILD360_SUPPORT_EMAIL", "").strip()
DEFAULT_FROM_EMAIL = BUILD360_TRANSACTIONAL_FROM_EMAIL
SERVER_EMAIL = BUILD360_TRANSACTIONAL_FROM_EMAIL
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.locmem.EmailBackend" if BUILD360_ENVIRONMENT == "testing" else (
        "django.core.mail.backends.console.EmailBackend"
        if BUILD360_ENVIRONMENT in {"development", "demo"}
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))


AI_LOCAL_ADAPTER_ENABLED = (
    BUILD360_ENVIRONMENT in {"testing", "demo"}
    or LOCAL_NO_DOCKER
    or os.getenv("AI_LOCAL_ADAPTER_ENABLED", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
AI_MAX_PROMPT_CHARACTERS = int(os.getenv("AI_MAX_PROMPT_CHARACTERS", "8000"))
AI_EXTRACTION_MAX_CHARACTERS = int(
    os.getenv("AI_EXTRACTION_MAX_CHARACTERS", "50000")
)
if not 500 <= AI_MAX_PROMPT_CHARACTERS <= 50000:
    raise ImproperlyConfigured(
        "AI_MAX_PROMPT_CHARACTERS must be between 500 and 50000"
    )
if not 1000 <= AI_EXTRACTION_MAX_CHARACTERS <= 500000:
    raise ImproperlyConfigured(
        "AI_EXTRACTION_MAX_CHARACTERS must be between 1000 and 500000"
    )


ADMINOPS_DEFAULT_REGION = os.getenv("ADMINOPS_DEFAULT_REGION", "local").strip() or "local"
ADMINOPS_HEALTH_RETENTION_DAYS = int(os.getenv("ADMINOPS_HEALTH_RETENTION_DAYS", "90"))
ADMINOPS_RELEASE_CHECKS_REQUIRED = (
    os.getenv("ADMINOPS_RELEASE_CHECKS_REQUIRED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
if not 1 <= ADMINOPS_HEALTH_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "ADMINOPS_HEALTH_RETENTION_DAYS must be between 1 and 3650"
    )

CONTROLPLANE_SUPPORT_MAX_HOURS = int(
    os.getenv("CONTROLPLANE_SUPPORT_MAX_HOURS", "24")
)
CONTROLPLANE_USAGE_RETENTION_DAYS = int(
    os.getenv("CONTROLPLANE_USAGE_RETENTION_DAYS", "400")
)

INTEGRATION_LOCAL_SIMULATION_ENABLED = (
    BUILD360_ENVIRONMENT in {"testing", "demo"}
    or LOCAL_NO_DOCKER
    or os.getenv("INTEGRATION_LOCAL_SIMULATION_ENABLED", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)
INTEGRATION_WEBHOOK_MAX_ATTEMPTS = int(
    os.getenv("INTEGRATION_WEBHOOK_MAX_ATTEMPTS", "5")
)
if INTEGRATION_WEBHOOK_MAX_ATTEMPTS < 1 or INTEGRATION_WEBHOOK_MAX_ATTEMPTS > 20:
    raise ImproperlyConfigured(
        "INTEGRATION_WEBHOOK_MAX_ATTEMPTS must be between 1 and 20"
    )
if not 1 <= CONTROLPLANE_SUPPORT_MAX_HOURS <= 168:
    raise ImproperlyConfigured(
        "CONTROLPLANE_SUPPORT_MAX_HOURS must be between 1 and 168"
    )
if not 30 <= CONTROLPLANE_USAGE_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "CONTROLPLANE_USAGE_RETENTION_DAYS must be between 30 and 3650"
    )

OBJECT_STORAGE_ENDPOINT = required("OBJECT_STORAGE_ENDPOINT")
OBJECT_STORAGE_PUBLIC_ENDPOINT = os.getenv(
    "OBJECT_STORAGE_PUBLIC_ENDPOINT", OBJECT_STORAGE_ENDPOINT
)
OBJECT_STORAGE_ACCESS_KEY = required("OBJECT_STORAGE_ACCESS_KEY")
OBJECT_STORAGE_SECRET_KEY = required("OBJECT_STORAGE_SECRET_KEY")
OBJECT_STORAGE_BUCKET = required("OBJECT_STORAGE_BUCKET")
OBJECT_STORAGE_REGION = os.getenv("OBJECT_STORAGE_REGION", "auto")
FILE_UPLOAD_MAX_BYTES = int(os.getenv("FILE_UPLOAD_MAX_BYTES", str(25 * 1024 * 1024)))
FILE_UPLOAD_URL_TTL_SECONDS = int(os.getenv("FILE_UPLOAD_URL_TTL_SECONDS", "900"))
FILE_DOWNLOAD_URL_TTL_SECONDS = int(os.getenv("FILE_DOWNLOAD_URL_TTL_SECONDS", "300"))
if FILE_UPLOAD_MAX_BYTES < 1 or FILE_UPLOAD_MAX_BYTES > 1024 * 1024 * 1024:
    raise ImproperlyConfigured("FILE_UPLOAD_MAX_BYTES must be between 1 byte and 1 GiB")
if not 60 <= FILE_UPLOAD_URL_TTL_SECONDS <= 3600:
    raise ImproperlyConfigured("FILE_UPLOAD_URL_TTL_SECONDS must be between 60 and 3600")
if not 60 <= FILE_DOWNLOAD_URL_TTL_SECONDS <= 3600:
    raise ImproperlyConfigured("FILE_DOWNLOAD_URL_TTL_SECONDS must be between 60 and 3600")

if BUILD360_ENVIRONMENT == "testing" or LOCAL_NO_DOCKER:
    REDIS_URL = os.getenv("REDIS_URL", "")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": (
                "build360-tests" if BUILD360_ENVIRONMENT == "testing" else f"build360-{BUILD360_ENVIRONMENT}-local-no-docker"
            ),
        }
    }
else:
    REDIS_URL = required("REDIS_URL")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

if LOCAL_NO_DOCKER:
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
else:
    CELERY_BROKER_URL = required("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = required("CELERY_RESULT_BACKEND")
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
if BUILD360_ENVIRONMENT == "production" or (BUILD360_ENVIRONMENT == "demo" and not LOCAL_NO_DOCKER):
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "modules.platform.logging.JsonFormatter",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


CLOUDOPS_DEPLOYMENT_EVIDENCE_REQUIRED = (
    os.getenv("CLOUDOPS_DEPLOYMENT_EVIDENCE_REQUIRED", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
CLOUDOPS_BACKUP_RETENTION_MIN_DAYS = int(
    os.getenv("CLOUDOPS_BACKUP_RETENTION_MIN_DAYS", "30")
)
CLOUDOPS_SECRET_ROTATION_WARNING_DAYS = int(
    os.getenv("CLOUDOPS_SECRET_ROTATION_WARNING_DAYS", "14")
)
if not 1 <= CLOUDOPS_BACKUP_RETENTION_MIN_DAYS <= 3650:
    raise ImproperlyConfigured(
        "CLOUDOPS_BACKUP_RETENTION_MIN_DAYS must be between 1 and 3650"
    )
if not 1 <= CLOUDOPS_SECRET_ROTATION_WARNING_DAYS <= 180:
    raise ImproperlyConfigured(
        "CLOUDOPS_SECRET_ROTATION_WARNING_DAYS must be between 1 and 180"
    )


COMPLIANCE_EXCEPTION_MAX_DAYS = int(
    os.getenv("COMPLIANCE_EXCEPTION_MAX_DAYS", "90")
)
COMPLIANCE_ASSESSMENT_RETENTION_DAYS = int(
    os.getenv("COMPLIANCE_ASSESSMENT_RETENTION_DAYS", "2555")
)
if not 1 <= COMPLIANCE_EXCEPTION_MAX_DAYS <= 365:
    raise ImproperlyConfigured(
        "COMPLIANCE_EXCEPTION_MAX_DAYS must be between 1 and 365"
    )
if not 365 <= COMPLIANCE_ASSESSMENT_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "COMPLIANCE_ASSESSMENT_RETENTION_DAYS must be between 365 and 3650"
    )


SUCCESSOPS_RENEWAL_WARNING_DAYS = int(
    os.getenv("SUCCESSOPS_RENEWAL_WARNING_DAYS", "90")
)
SUCCESSOPS_SUPPORT_RETENTION_DAYS = int(
    os.getenv("SUCCESSOPS_SUPPORT_RETENTION_DAYS", "1095")
)
if not 1 <= SUCCESSOPS_RENEWAL_WARNING_DAYS <= 365:
    raise ImproperlyConfigured(
        "SUCCESSOPS_RENEWAL_WARNING_DAYS must be between 1 and 365"
    )
if not 365 <= SUCCESSOPS_SUPPORT_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "SUCCESSOPS_SUPPORT_RETENTION_DAYS must be between 365 and 3650"
    )


PEOPLEOPS_PAYROLL_RETENTION_DAYS = int(
    os.getenv("PEOPLEOPS_PAYROLL_RETENTION_DAYS", "2555")
)
PEOPLEOPS_LEAVE_YEAR_START_MONTH = int(
    os.getenv("PEOPLEOPS_LEAVE_YEAR_START_MONTH", "1")
)
if not 365 <= PEOPLEOPS_PAYROLL_RETENTION_DAYS <= 3650:
    raise ImproperlyConfigured(
        "PEOPLEOPS_PAYROLL_RETENTION_DAYS must be between 365 and 3650"
    )
if not 1 <= PEOPLEOPS_LEAVE_YEAR_START_MONTH <= 12:
    raise ImproperlyConfigured(
        "PEOPLEOPS_LEAVE_YEAR_START_MONTH must be between 1 and 12"
    )
# Build360 Experience / white-label domain foundation.
# Application mapping only. Production DNS/wildcard routing/TLS require deployment evidence.
BUILD360_PLATFORM_DOMAIN_SUFFIX = os.getenv(
    "BUILD360_PLATFORM_DOMAIN_SUFFIX", "build360.local"
).strip().lower().strip(".")
BUILD360_CUSTOM_DOMAIN_CNAME_TARGET = os.getenv(
    "BUILD360_CUSTOM_DOMAIN_CNAME_TARGET", "domains.build360.local"
).strip().lower().rstrip(".")
