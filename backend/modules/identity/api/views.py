import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.identity.application.password_reset import (
    complete_password_reset,
    issue_password_reset_token,
)
from modules.identity.application.password_reset_delivery import deliver_password_reset_email
from modules.identity.application.password_reset_policy import password_reset_delivery_mode
from modules.identity.application.tokens import (
    AccessPrincipal,
    TokenPair,
    issue_session,
    revoke_session,
    rotate_refresh_token,
)
from modules.identity.models import AuthSession, User
from modules.platform.audit import AuditRecord, append_audit, request_metadata
from modules.tenant.application.email_delivery import resolve_password_reset_scope
from modules.tenant.models import Membership

from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    RevokeSessionSerializer,
)
from .throttling import LoginThrottle, PasswordResetThrottle, RefreshThrottle


def token_response(pair: TokenPair) -> dict[str, object]:
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "token_type": "Bearer",
        "access_expires_at": pair.access_expires_at.isoformat(),
        "refresh_expires_at": pair.refresh_expires_at.isoformat(),
        "session_public_id": str(pair.session_public_id),
    }


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type] = []
    throttle_classes = [LoginThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, ip_address, user_agent = request_metadata(request._request)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.is_active or not user.check_password(
            serializer.validated_data["password"]
        ):
            append_audit(
                AuditRecord(
                    action="identity.login.failed",
                    entity_type="user",
                    actor_type="anonymous",
                    request_id=request_id,
                    correlation_id=request_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    reason_code="invalid_credentials",
                )
            )
            raise AuthenticationFailed("Invalid credentials")

        with transaction.atomic():
            pair = issue_session(
                user=user,
                device_id=serializer.validated_data["device_id"],
                device_name=serializer.validated_data["device_name"],
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=request_id,
            )
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
        return Response(token_response(pair))


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type] = []
    throttle_classes = [PasswordResetThrottle]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        payload: dict[str, object] = {
            "message": "If an active Build360 account exists for this email, password reset instructions are available.",
        }
        if user is not None:
            delivery_mode = password_reset_delivery_mode(
                getattr(settings, "BUILD360_ENVIRONMENT", "development")
            )
            if delivery_mode == "INLINE":
                # Demo/local development is deliberately email-free. The BFF converts
                # these one-time values into a same-origin reset link for the UI.
                uid, token = issue_password_reset_token(
                    user=user,
                    correlation_id=request_id,
                )
                payload["debug_uid"] = uid
                payload["debug_token"] = token
            else:
                # Testing and production never return reset token material to the UI.
                # They use the governed platform/tenant transactional mail route only.
                public_host = str(
                    request.META.get("HTTP_X_BUILD360_PUBLIC_HOST")
                    or request.META.get("HTTP_HOST")
                    or ""
                )
                scope = resolve_password_reset_scope(
                    user=user,
                    public_host=public_host,
                )
                if scope.allowed:
                    uid, token = issue_password_reset_token(
                        user=user,
                        correlation_id=request_id,
                    )
                    deliver_password_reset_email(
                        user=user,
                        uid=uid,
                        token=token,
                        correlation_id=request_id,
                        scope=scope,
                    )
        return Response(payload, status=202)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type] = []
    throttle_classes = [PasswordResetThrottle]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        user = complete_password_reset(
            uid=serializer.validated_data["uid"],
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["password"],
            correlation_id=request_id,
        )
        if user is None:
            return Response({"message": "This password reset link is invalid or has expired."}, status=400)
        return Response({"message": "Password updated. Sign in with your new password."})


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type] = []
    throttle_classes = [RefreshThrottle]

    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, ip_address, user_agent = request_metadata(request._request)
        pair = rotate_refresh_token(
            encoded_token=serializer.validated_data["refresh_token"],
            correlation_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return Response(token_response(pair))


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        serializer = RevokeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not isinstance(request.auth, AccessPrincipal):
            raise AuthenticationFailed("An authenticated session is required")
        request_id = getattr(request, "request_id", uuid.uuid4())
        revoke_session(
            session=request.auth.session,
            actor_public_id=request.auth.user.public_id,
            reason=serializer.validated_data["reason_code"],
            correlation_id=request_id,
        )
        return Response(status=204)


class MeView(APIView):
    def get(self, request: Request) -> Response:
        if not isinstance(request.auth, AccessPrincipal):
            raise AuthenticationFailed("An authenticated session is required")
        user = request.auth.user
        memberships = (
            Membership.objects.filter(
                user=user,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                company__is_active=True,
            )
            .select_related("company")
            .order_by("company__display_name")
        )
        return Response(
            {
                "user": {
                    "public_id": str(user.public_id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "preferred_locale": user.preferred_locale,
                },
                "memberships": [
                    {
                        "public_id": str(membership.public_id),
                        "company": {
                            "public_id": str(membership.company.public_id),
                            "code": membership.company.code,
                            "display_name": membership.company.display_name,
                            "locale": membership.company.locale,
                            "timezone": membership.company.timezone,
                        },
                    }
                    for membership in memberships
                ],
            }
        )


class SessionListView(APIView):
    def get(self, request: Request) -> Response:
        if not isinstance(request.auth, AccessPrincipal):
            raise AuthenticationFailed("An authenticated session is required")
        sessions = AuthSession.objects.filter(user=request.auth.user).order_by("-created_at")[
            :100
        ]
        return Response(
            {
                "items": [
                    {
                        "public_id": str(session.public_id),
                        "device_id": str(session.device_id),
                        "device_name": session.device_name,
                        "created_at": session.created_at.isoformat(),
                        "expires_at": session.expires_at.isoformat(),
                        "revoked_at": (
                            session.revoked_at.isoformat() if session.revoked_at else None
                        ),
                    }
                    for session in sessions
                ]
            }
        )


class SessionRevokeView(APIView):
    def post(self, request: Request, session_id: uuid.UUID) -> Response:
        if not isinstance(request.auth, AccessPrincipal):
            raise AuthenticationFailed("An authenticated session is required")
        session = AuthSession.objects.filter(
            public_id=session_id,
            user=request.auth.user,
        ).first()
        if not session:
            from rest_framework.exceptions import NotFound

            raise NotFound("Resource not found")
        serializer = RevokeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = getattr(request, "request_id", uuid.uuid4())
        revoke_session(
            session=session,
            actor_public_id=request.auth.user.public_id,
            reason=serializer.validated_data["reason_code"],
            correlation_id=request_id,
        )
        return Response(status=204)
