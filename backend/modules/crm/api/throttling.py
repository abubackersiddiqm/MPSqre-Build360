from __future__ import annotations

import hashlib

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle


class CrmContactRevealThrottle(SimpleRateThrottle):
    """Limit protected contact reveals per authenticated user and tenant."""

    scope = "crm_contact_reveal"

    def get_cache_key(self, request: Request, view: object) -> str | None:
        principal = getattr(request, "auth", None)
        user = getattr(principal, "user", None)
        if user is None:
            return None
        company_id = str(request.META.get("HTTP_X_COMPANY_ID", "")).strip().lower()
        identity = hashlib.sha256(
            f"{getattr(user, 'public_id', user.pk)}:{company_id}".encode()
        ).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": identity}
