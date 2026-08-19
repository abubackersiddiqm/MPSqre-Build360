import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.configuration.application.services import (
    create_configuration_draft,
    get_active_configuration,
    list_active_configurations,
    publish_configuration_version,
)
from modules.configuration.models import (
    ConfigurationDefinition,
    ConfigurationVersion,
)
from modules.platform.audit import request_metadata
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import ConfigurationDraftSerializer


def _version_response(version: object, *, include_payload: bool) -> dict[str, object]:
    from modules.configuration.models import ConfigurationVersion

    assert isinstance(version, ConfigurationVersion)
    result: dict[str, object] = {
        "public_id": str(version.public_id),
        "definition_code": version.definition.code,
        "name": version.definition.name,
        "version": version.version,
        "status": version.status,
        "effective_from": version.effective_from.isoformat(),
        "effective_to": version.effective_to.isoformat() if version.effective_to else None,
        "checksum": version.checksum,
        "is_secret": version.definition.is_secret,
    }
    if include_payload:
        result["payload"] = version.payload
    return result


class ActiveConfigurationListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("configuration.read")
        items = []
        for version in list_active_configurations(company=self.tenant_context.company):
            include_payload = not version.definition.is_secret or self.tenant_context.can(
                "configuration.secret.read"
            )
            items.append(_version_response(version, include_payload=include_payload))
        return Response({"items": items})


class ActiveConfigurationDetailView(TenantScopedAPIView):
    def get(self, request: Request, code: str) -> Response:
        self.tenant_context.require("configuration.read")
        version = get_active_configuration(
            company=self.tenant_context.company,
            definition_code=code,
        )
        if not version:
            raise NotFound("Resource not found")
        include_payload = not version.definition.is_secret or self.tenant_context.can(
            "configuration.secret.read"
        )
        return Response(_version_response(version, include_payload=include_payload))


class ConfigurationDraftCreateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("configuration.manage")
        serializer = ConfigurationDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        definition = ConfigurationDefinition.objects.filter(
            code=serializer.validated_data["definition_code"],
            is_active=True,
        ).first()
        if not definition:
            raise NotFound("Resource not found")
        request_id, _, _ = request_metadata(request._request)
        try:
            version = create_configuration_draft(
                company=self.tenant_context.company,
                definition=definition,
                payload=serializer.validated_data["payload"],
                effective_from=serializer.validated_data["effective_from"],
                effective_to=serializer.validated_data.get("effective_to"),
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            _version_response(
                version,
                include_payload=(
                    not definition.is_secret
                    or self.tenant_context.can("configuration.secret.read")
                ),
            ),
            status=201,
        )


class ConfigurationPublishView(TenantScopedAPIView):
    def post(self, request: Request, version_id: uuid.UUID) -> Response:
        self.tenant_context.require("configuration.publish")
        if not ConfigurationVersion.objects.filter(
            public_id=version_id,
            company=self.tenant_context.company,
        ).exists():
            raise NotFound("Resource not found")
        request_id, _, _ = request_metadata(request._request)
        try:
            version = publish_configuration_version(
                version_public_id=version_id,
                company=self.tenant_context.company,
                actor_public_id=self.tenant_context.principal.user.public_id,
                correlation_id=request_id,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            _version_response(
                version,
                include_payload=(
                    not version.definition.is_secret
                    or self.tenant_context.can("configuration.secret.read")
                ),
            )
        )
