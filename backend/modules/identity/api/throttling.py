import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request: object, view: object) -> str | None:
        from rest_framework.request import Request

        if not isinstance(request, Request):
            return None
        data = request.data
        email = (
            str(data.get("email", "")).strip().lower()
            if isinstance(data, dict)
            else ""
        )
        address = self.get_ident(request)
        identity = hashlib.sha256(f"{address}:{email}".encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": identity}


class RefreshThrottle(SimpleRateThrottle):
    scope = "refresh"

    def get_cache_key(self, request: object, view: object) -> str | None:
        from rest_framework.request import Request

        if not isinstance(request, Request):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PasswordResetThrottle(LoginThrottle):
    scope = "password_reset"
