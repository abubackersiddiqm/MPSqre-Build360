from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.audit import request_metadata
from modules.subscription.application.entitlements import effective_entitlements
from modules.subscription.application.overrides import create_entitlement_override
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import EntitlementOverrideSerializer


class EffectiveEntitlementsView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("subscription.read")
        effective = effective_entitlements(company=self.tenant_context.company)
        return Response(
            {
                "subscription_status": effective.subscription_status,
                "plan_code": effective.plan_code,
                "plan_version": effective.plan_version,
                "entitlements": effective.entitlements,
                "limits": effective.limits,
            }
        )


class EntitlementOverrideCreateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("subscription.manage")
        serializer = EntitlementOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id, _, _ = request_metadata(request._request)
        try:
            override = create_entitlement_override(
                company=self.tenant_context.company,
                entitlement_code=serializer.validated_data["entitlement_code"],
                enabled=serializer.validated_data["enabled"],
                limit_value=serializer.validated_data.get("limit_value"),
                effective_from=serializer.validated_data["effective_from"],
                effective_to=serializer.validated_data.get("effective_to"),
                reason_code=serializer.validated_data["reason_code"],
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            {
                "public_id": str(override.public_id),
                "entitlement_code": override.entitlement_code,
                "enabled": override.enabled,
                "limit_value": override.limit_value,
                "effective_from": override.effective_from.isoformat(),
                "effective_to": (
                    override.effective_to.isoformat() if override.effective_to else None
                ),
            },
            status=201,
        )
