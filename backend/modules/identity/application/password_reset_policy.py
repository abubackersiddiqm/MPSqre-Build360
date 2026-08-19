from __future__ import annotations

INLINE_RESET_LINK_ENVIRONMENTS = frozenset({"demo", "development"})


def password_reset_delivery_mode(environment: str | None) -> str:
    normalized = str(environment or "development").strip().lower()
    return "INLINE" if normalized in INLINE_RESET_LINK_ENVIRONMENTS else "EMAIL"
