from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from modules.identity.application.tokens import AccessPrincipal, authenticate_access_token
from modules.identity.models import User


class JwtAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[User, AccessPrincipal] | None:
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != self.keyword:
            raise AuthenticationFailed("Authorization header is invalid")
        try:
            encoded_token = header[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise AuthenticationFailed("Authorization header is invalid") from exc
        principal = authenticate_access_token(encoded_token)
        return principal.user, principal

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
