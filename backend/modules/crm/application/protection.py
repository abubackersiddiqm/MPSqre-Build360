from __future__ import annotations

import hashlib
import hmac
import re

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

_SPACE_RE = re.compile(r"\s+")
_NON_DIGIT_RE = re.compile(r"\D+")


def normalize_email(value: str) -> str:
    return _SPACE_RE.sub("", value).strip().lower()


def normalize_phone(value: str) -> str:
    normalized = _NON_DIGIT_RE.sub("", value)
    if value.strip().startswith("+"):
        normalized = f"+{normalized}"
    return normalized


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _protector() -> MultiFernet:
    try:
        return MultiFernet(
            [Fernet(key.encode("ascii")) for key in settings.CRM_PROTECTED_DATA_KEYS]
        )
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "CRM_PROTECTED_DATA_KEYS contains an invalid Fernet key"
        ) from exc


def encrypt_value(value: str) -> str:
    if not value:
        return ""
    return _protector().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_value(value: str) -> str:
    if not value:
        return ""
    try:
        return _protector().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("Protected contact value could not be decrypted") from exc


def blind_index(value: str, *, purpose: str) -> str:
    if not value:
        return ""
    key = settings.CRM_BLIND_INDEX_KEY.encode("utf-8")
    payload = f"{purpose}:{value}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def masked_email(last_four: str) -> str | None:
    return f"••••{last_four}" if last_four else None


def masked_phone(last_four: str) -> str | None:
    return f"••••{last_four}" if last_four else None
