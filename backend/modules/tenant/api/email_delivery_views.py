from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.platform.audit import AuditRecord, append_audit
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.api.email_delivery_serializers import (
    EmailDeliveryTestSerializer,
    EmailDeliveryUpdateSerializer,
)
from modules.tenant.application.email_delivery import (
    encrypt_smtp_password,
    resolve_transactional_brand,
    test_company_smtp,
)
from modules.tenant.models import CompanyEmailDeliveryProfile


def _require_white_label(company) -> None:
    if not feature_enabled(company=company, code="tenant.white_label"):
        raise PermissionDenied("White Label is disabled for this company subscription")


def _profile(company) -> CompanyEmailDeliveryProfile:
    return (
        CompanyEmailDeliveryProfile.objects.filter(company=company).first()
        or CompanyEmailDeliveryProfile(company=company)
    )


def _payload(profile: CompanyEmailDeliveryProfile) -> dict[str, object]:
    active = (
        profile.delivery_mode == CompanyEmailDeliveryProfile.DeliveryMode.TENANT_SMTP
        and profile.status == CompanyEmailDeliveryProfile.Status.ACTIVE
        and profile.verified_at is not None
    )
    return {
        "public_id": str(profile.public_id),
        "delivery_mode": profile.delivery_mode,
        "smtp_host": profile.smtp_host,
        "smtp_port": profile.smtp_port,
        "smtp_username": profile.smtp_username,
        "password_configured": bool(profile.smtp_password_encrypted),
        "smtp_use_tls": profile.smtp_use_tls,
        "smtp_use_ssl": profile.smtp_use_ssl,
        "from_email": profile.from_email,
        "reply_to_email": profile.reply_to_email,
        "status": profile.status,
        "effective_route": "TENANT_SMTP" if active else "PLATFORM",
        "last_tested_at": profile.last_tested_at,
        "verified_at": profile.verified_at,
        "last_error_code": profile.last_error_code,
        "version": profile.version,
    }


def _audit(request: Request, tenant_context, *, action: str, profile) -> None:
    actor = request_actor(request, tenant_context)
    append_audit(
        AuditRecord(
            action=action,
            entity_type="company_email_delivery_profile",
            entity_public_id=profile.public_id,
            company_public_id=tenant_context.company.public_id,
            actor_type="user",
            actor_public_id=actor.user_public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after={
                "delivery_mode": profile.delivery_mode,
                "smtp_host": profile.smtp_host,
                "smtp_port": profile.smtp_port,
                "smtp_use_tls": profile.smtp_use_tls,
                "smtp_use_ssl": profile.smtp_use_ssl,
                "from_email": profile.from_email,
                "status": profile.status,
                "version": profile.version,
                "password_configured": bool(profile.smtp_password_encrypted),
            },
        )
    )


class CurrentEmailDeliveryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.read")
        _require_white_label(self.tenant_context.company)
        return Response(_payload(_profile(self.tenant_context.company)))

    def patch(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.manage")
        _require_white_label(self.tenant_context.company)
        serializer = EmailDeliveryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        expected_version = data.pop("expected_version")
        password = data.pop("smtp_password", "")
        clear_password = data.pop("clear_password", False)
        actor = request_actor(request, self.tenant_context)

        try:
            with transaction.atomic():
                profile, _ = CompanyEmailDeliveryProfile.objects.select_for_update().get_or_create(
                    company=self.tenant_context.company
                )
                if profile.version != expected_version:
                    raise ValidationError(
                        {"expected_version": ["Email settings changed in another session. Refresh and retry."]}
                    )
                for key, value in data.items():
                    setattr(profile, key, value)
                if clear_password:
                    profile.smtp_password_encrypted = ""
                elif password:
                    profile.smtp_password_encrypted = encrypt_smtp_password(password)

                profile.updated_by_public_id = actor.user_public_id
                profile.last_error_code = ""
                profile.last_tested_at = None
                profile.verified_at = None
                profile.status = (
                    CompanyEmailDeliveryProfile.Status.PENDING
                    if profile.delivery_mode == CompanyEmailDeliveryProfile.DeliveryMode.TENANT_SMTP
                    else CompanyEmailDeliveryProfile.Status.DISABLED
                )
                profile.version += 1
                profile.full_clean()
                profile.save()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError(exc.messages) from exc

        _audit(request, self.tenant_context, action="tenant.email_delivery.updated", profile=profile)
        return Response(_payload(profile))


class CurrentEmailDeliveryTestView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.manage")
        _require_white_label(self.tenant_context.company)
        serializer = EmailDeliveryTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]

        profile = CompanyEmailDeliveryProfile.objects.filter(
            company=self.tenant_context.company
        ).first()
        if profile is None:
            raise ValidationError({"detail": "Save company email settings first."})
        if profile.version != expected_version:
            raise ValidationError(
                {"expected_version": ["Email settings changed in another session. Refresh and retry."]}
            )
        brand = resolve_transactional_brand(self.tenant_context.company)
        recipient = self.tenant_context.principal.user.email

        # Network I/O is deliberately outside a database transaction.
        result = test_company_smtp(
            profile=profile,
            recipient=recipient,
            sender_name=brand.sender_name,
        )

        with transaction.atomic():
            profile = CompanyEmailDeliveryProfile.objects.select_for_update().get(
                company=self.tenant_context.company
            )
            if profile.version != expected_version:
                raise ValidationError(
                    {"expected_version": ["Email settings changed while the connection test was running. Refresh and retry."]}
                )
            now = timezone.now()
            profile.last_tested_at = now
            profile.last_error_code = result.error_code
            if result.status == "SENT":
                profile.status = CompanyEmailDeliveryProfile.Status.ACTIVE
                profile.verified_at = now
            else:
                profile.status = CompanyEmailDeliveryProfile.Status.FAILED
                profile.verified_at = None
            profile.version += 1
            profile.full_clean()
            profile.save()

        _audit(request, self.tenant_context, action="tenant.email_delivery.tested", profile=profile)
        payload = _payload(profile)
        payload["test_sent_to"] = recipient
        payload["message"] = (
            "Company SMTP verified and activated."
            if result.status == "SENT"
            else "Company SMTP test failed. Build360 platform mail remains the fallback."
        )
        return Response(payload, status=200 if result.status == "SENT" else 400)
