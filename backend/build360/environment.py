from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

ENVIRONMENT_ALIASES = {
    "local": "development",
    "dev": "development",
    "development": "development",
    "test": "testing",
    "tests": "testing",
    "testing": "testing",
    "demo": "demo",
    "production": "production",
    "prod": "production",
}
SUPPORTED_ENVIRONMENTS = ("development", "testing", "demo", "production")


def normalize_environment(value: str | None, *, default: str = "development") -> str:
    raw = (value or default).strip().lower()
    normalized = ENVIRONMENT_ALIASES.get(raw)
    if normalized is None:
        allowed = ", ".join(SUPPORTED_ENVIRONMENTS)
        raise ImproperlyConfigured(
            f"Unsupported Build360 environment '{raw}'. Use one of: {allowed}."
        )
    return normalized


def _resolve_explicit_path(value: str, project_root: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def selected_environment_from_process() -> str:
    explicit = os.getenv("BUILD360_ENVIRONMENT", "").strip()
    if explicit:
        return normalize_environment(explicit)
    legacy = os.getenv("APP_ENV", "").strip()
    return normalize_environment(legacy or "development")


def load_project_environment(base_dir: Path) -> Path | None:
    """Load exactly one Build360 environment file without overriding process vars.

    Resolution order:
    1. DJANGO_ENV_FILE, resolved relative to the project root when not absolute.
    2. backend/.env.<environment> for the selected BUILD360_ENVIRONMENT.
    3. project-root/.env.<environment> for container/deployment layouts.
    4. Legacy backend/.env and project-root/.env fallbacks.

    Environment selection defaults to development when neither BUILD360_ENVIRONMENT
    nor legacy APP_ENV is already present in the process. Existing process variables
    always take precedence because python-dotenv is loaded with override=False.
    """

    project_root = base_dir.parent
    explicit_file = os.getenv("DJANGO_ENV_FILE", "").strip()
    if explicit_file:
        env_path = _resolve_explicit_path(explicit_file, project_root)
        if not env_path.is_file():
            raise ImproperlyConfigured(
                f"DJANGO_ENV_FILE does not point to a readable file: {env_path}"
            )
    else:
        selected = selected_environment_from_process()
        env_path = next(
            (
                candidate
                for candidate in (
                    base_dir / f".env.{selected}",
                    project_root / f".env.{selected}",
                    base_dir / ".env",
                    project_root / ".env",
                )
                if candidate.is_file()
            ),
            None,
        )
        if env_path is None:
            return None

    load_dotenv(dotenv_path=env_path, override=False, encoding="utf-8")
    os.environ["DJANGO_ENV_FILE_LOADED"] = str(env_path)
    return env_path
