from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.sustainabilityops.application.selectors import sustainability_overview
from modules.sustainabilityops.application.services import (
    create_assessment,
    create_disclosure,
    create_factor,
    create_initiative,
    create_inventory,
    create_target,
    record_activity,
    record_resource,
    record_waste,
    seed_defaults,
    transition_activity,
    transition_assessment,
    transition_disclosure,
    transition_initiative,
    transition_inventory,
    transition_target,
)
from modules.sustainabilityops.models import (
    AssuranceAssessment,
    CarbonActivity,
    CarbonInventory,
    DisclosureReport,
    EmissionFactor,
    ESGInitiative,
    SustainabilityTarget,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    ActivityCreateSerializer,
    ActivityTransitionSerializer,
    AssessmentCreateSerializer,
    DisclosureCreateSerializer,
    FactorCreateSerializer,
    InitiativeCreateSerializer,
    InitiativeTransitionSerializer,
    InventoryCreateSerializer,
    LifecycleTransitionSerializer,
    ResourceCreateSerializer,
    TargetCreateSerializer,
    TargetTransitionSerializer,
    WasteCreateSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if item is None:
        raise NotFound(message)
    return item


class SustainabilityAPIView(TenantScopedAPIView):
    required_permission = "sustainability.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(SustainabilityAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(sustainability_overview(self.tenant_context.company))


class FactorCreateView(SustainabilityAPIView):
    required_permission = "sustainability.factor"

    def post(self, request: Request) -> Response:
        serializer = FactorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_factor(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class ActivityCreateView(SustainabilityAPIView):
    required_permission = "sustainability.activity"

    def post(self, request: Request) -> Response:
        serializer = ActivityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        factor = find(
            EmissionFactor,
            company=self.tenant_context.company,
            public_id=data.pop("factor_public_id"),
            message="Emission factor not found.",
        )
        if not data.get("activity_unit_code"):
            data["activity_unit_code"] = factor.activity_unit_code
        try:
            item = record_activity(
                company=self.tenant_context.company,
                factor=factor,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {"public_id": str(item.public_id), "kg_co2e": str(item.calculated_kg_co2e), "status": item.status_code},
            status=201,
        )


class ActivityTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.assure"

    def post(self, request: Request, activity_id: uuid.UUID) -> Response:
        activity = find(
            CarbonActivity,
            company=self.tenant_context.company,
            public_id=activity_id,
            message="Carbon activity not found.",
        )
        serializer = ActivityTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            activity = transition_activity(
                activity=activity,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(activity.public_id), "status": activity.status_code, "version": activity.version})


class InventoryCreateView(SustainabilityAPIView):
    required_permission = "sustainability.inventory"

    def post(self, request: Request) -> Response:
        serializer = InventoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_inventory(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response(
            {"public_id": str(item.public_id), "code": item.code, "net_kg_co2e": str(item.net_kg_co2e)},
            status=201,
        )


class InventoryTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.assure"

    def post(self, request: Request, inventory_id: uuid.UUID) -> Response:
        inventory = find(
            CarbonInventory,
            company=self.tenant_context.company,
            public_id=inventory_id,
            message="Carbon inventory not found.",
        )
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            inventory = transition_inventory(
                inventory=inventory,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(inventory.public_id), "status": inventory.status_code, "version": inventory.version})


class ResourceCreateView(SustainabilityAPIView):
    required_permission = "sustainability.resource"

    def post(self, request: Request) -> Response:
        serializer = ResourceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_resource(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id)}, status=201)


class WasteCreateView(SustainabilityAPIView):
    required_permission = "sustainability.waste"

    def post(self, request: Request) -> Response:
        serializer = WasteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_waste(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id)}, status=201)


class TargetCreateView(SustainabilityAPIView):
    required_permission = "sustainability.target"

    def post(self, request: Request) -> Response:
        serializer = TargetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_target(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class TargetTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.target"

    def post(self, request: Request, target_id: uuid.UUID) -> Response:
        target = find(
            SustainabilityTarget,
            company=self.tenant_context.company,
            public_id=target_id,
            message="Sustainability target not found.",
        )
        serializer = TargetTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = transition_target(
                target=target,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(target.public_id), "status": target.status_code, "version": target.version})


class InitiativeCreateView(SustainabilityAPIView):
    required_permission = "sustainability.target"

    def post(self, request: Request) -> Response:
        serializer = InitiativeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        target_id = data.pop("target_public_id", None)
        target = (
            find(
                SustainabilityTarget,
                company=self.tenant_context.company,
                public_id=target_id,
                message="Sustainability target not found.",
            )
            if target_id
            else None
        )
        try:
            item = create_initiative(
                company=self.tenant_context.company,
                target=target,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class InitiativeTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.target"

    def post(self, request: Request, initiative_id: uuid.UUID) -> Response:
        initiative = find(
            ESGInitiative,
            company=self.tenant_context.company,
            public_id=initiative_id,
            message="ESG initiative not found.",
        )
        serializer = InitiativeTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            initiative = transition_initiative(
                initiative=initiative,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(initiative.public_id), "status": initiative.status_code, "version": initiative.version})


class AssessmentCreateView(SustainabilityAPIView):
    required_permission = "sustainability.assure"

    def post(self, request: Request) -> Response:
        serializer = AssessmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_assessment(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class AssessmentTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.assure"

    def post(self, request: Request, assessment_id: uuid.UUID) -> Response:
        assessment = find(
            AssuranceAssessment,
            company=self.tenant_context.company,
            public_id=assessment_id,
            message="Assurance assessment not found.",
        )
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assessment = transition_assessment(
                assessment=assessment,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(assessment.public_id), "status": assessment.status_code, "version": assessment.version})


class DisclosureCreateView(SustainabilityAPIView):
    required_permission = "sustainability.report"

    def post(self, request: Request) -> Response:
        serializer = DisclosureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_disclosure(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class DisclosureTransitionView(SustainabilityAPIView):
    required_permission = "sustainability.assure"

    def post(self, request: Request, disclosure_id: uuid.UUID) -> Response:
        disclosure = find(
            DisclosureReport,
            company=self.tenant_context.company,
            public_id=disclosure_id,
            message="Disclosure report not found.",
        )
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            disclosure = transition_disclosure(
                disclosure=disclosure,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(disclosure.public_id), "status": disclosure.status_code, "version": disclosure.version})
