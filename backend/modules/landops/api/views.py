from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.landops.application.selectors import land_acquisition_overview
from modules.landops.application.services import (
    create_approval,
    create_diligence,
    create_event,
    create_feasibility,
    create_offer,
    create_opportunity,
    create_ownership,
    create_parcel,
    create_risk,
    seed_defaults,
    transition_approval,
    transition_diligence,
    transition_feasibility,
    transition_offer,
    transition_opportunity,
    transition_risk,
    verify_ownership,
)
from modules.landops.models import (
    AcquisitionOpportunity,
    CommercialOffer,
    DueDiligenceCase,
    FeasibilityScenario,
    LandParcel,
    LandRisk,
    OwnershipInterest,
    StatutoryApproval,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    ApprovalCreateSerializer,
    DiligenceCreateSerializer,
    EventCreateSerializer,
    FeasibilityCreateSerializer,
    LifecycleTransitionSerializer,
    OfferCreateSerializer,
    OpportunityCreateSerializer,
    OwnershipCreateSerializer,
    ParcelCreateSerializer,
    RiskCreateSerializer,
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


class LandAPIView(TenantScopedAPIView):
    required_permission = "land.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(LandAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(land_acquisition_overview(self.tenant_context.company))


class ParcelCreateView(LandAPIView):
    required_permission = "land.parcel"

    def post(self, request: Request) -> Response:
        serializer = ParcelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_parcel(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "parcel_code": item.parcel_code}, status=201)


class OwnershipCreateView(LandAPIView):
    required_permission = "land.title"

    def post(self, request: Request) -> Response:
        serializer = OwnershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        try:
            item = create_ownership(company=self.tenant_context.company, parcel=parcel, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "owner_name": item.owner_name}, status=201)


class OwnershipTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, ownership_id: uuid.UUID) -> Response:
        item = find(OwnershipInterest, company=self.tenant_context.company, public_id=ownership_id, message="Ownership interest not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = verify_ownership(ownership=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.verification_status_code, "version": item.version})


class DiligenceCreateView(LandAPIView):
    required_permission = "land.diligence"

    def post(self, request: Request) -> Response:
        serializer = DiligenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        if not data.get("opened_on"):
            data.pop("opened_on", None)
        if not data.get("target_on"):
            data.pop("target_on", None)
        try:
            item = create_diligence(company=self.tenant_context.company, parcel=parcel, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "case_number": item.case_number}, status=201)


class DiligenceTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, case_id: uuid.UUID) -> Response:
        item = find(DueDiligenceCase, company=self.tenant_context.company, public_id=case_id, message="Due-diligence case not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_diligence(case=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class FeasibilityCreateView(LandAPIView):
    required_permission = "land.feasibility"

    def post(self, request: Request) -> Response:
        serializer = FeasibilityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_feasibility(company=self.tenant_context.company, parcel=parcel, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "scenario_code": item.scenario_code, "projected_margin_percent": str(item.projected_margin_percent)}, status=201)


class FeasibilityTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, scenario_id: uuid.UUID) -> Response:
        item = find(FeasibilityScenario, company=self.tenant_context.company, public_id=scenario_id, message="Feasibility scenario not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_feasibility(scenario=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class OpportunityCreateView(LandAPIView):
    required_permission = "land.acquisition"

    def post(self, request: Request) -> Response:
        serializer = OpportunityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        feasibility_id = data.pop("feasibility_public_id", None)
        feasibility = find(FeasibilityScenario, company=self.tenant_context.company, public_id=feasibility_id, message="Feasibility scenario not found.") if feasibility_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_opportunity(company=self.tenant_context.company, parcel=parcel, feasibility=feasibility, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "opportunity_code": item.opportunity_code}, status=201)


class OpportunityTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, opportunity_id: uuid.UUID) -> Response:
        item = find(AcquisitionOpportunity, company=self.tenant_context.company, public_id=opportunity_id, message="Acquisition opportunity not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_opportunity(opportunity=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "stage": item.stage_code, "version": item.version})


class OfferCreateView(LandAPIView):
    required_permission = "land.acquisition"

    def post(self, request: Request) -> Response:
        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        opportunity = find(AcquisitionOpportunity, company=self.tenant_context.company, public_id=data.pop("opportunity_public_id"), message="Acquisition opportunity not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_offer(company=self.tenant_context.company, opportunity=opportunity, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "offer_number": item.offer_number}, status=201)


class OfferTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, offer_id: uuid.UUID) -> Response:
        item = find(CommercialOffer, company=self.tenant_context.company, public_id=offer_id, message="Commercial offer not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_offer(offer=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class ApprovalCreateView(LandAPIView):
    required_permission = "land.approval"

    def post(self, request: Request) -> Response:
        serializer = ApprovalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        opportunity_id = data.pop("opportunity_public_id", None)
        opportunity = find(AcquisitionOpportunity, company=self.tenant_context.company, public_id=opportunity_id, message="Acquisition opportunity not found.") if opportunity_id else None
        try:
            item = create_approval(company=self.tenant_context.company, parcel=parcel, opportunity=opportunity, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "approval_code": item.approval_code}, status=201)


class ApprovalTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, approval_id: uuid.UUID) -> Response:
        item = find(StatutoryApproval, company=self.tenant_context.company, public_id=approval_id, message="Statutory approval not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_approval(approval=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class RiskCreateView(LandAPIView):
    required_permission = "land.risk"

    def post(self, request: Request) -> Response:
        serializer = RiskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        parcel = find(LandParcel, company=self.tenant_context.company, public_id=data.pop("parcel_public_id"), message="Land parcel not found.")
        opportunity_id = data.pop("opportunity_public_id", None)
        opportunity = find(AcquisitionOpportunity, company=self.tenant_context.company, public_id=opportunity_id, message="Acquisition opportunity not found.") if opportunity_id else None
        try:
            item = create_risk(company=self.tenant_context.company, parcel=parcel, opportunity=opportunity, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "risk_number": item.risk_number}, status=201)


class RiskTransitionView(LandAPIView):
    required_permission = "land.approve"

    def post(self, request: Request, risk_id: uuid.UUID) -> Response:
        item = find(LandRisk, company=self.tenant_context.company, public_id=risk_id, message="Land risk not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_risk(risk=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class EventCreateView(LandAPIView):
    required_permission = "land.acquisition"

    def post(self, request: Request) -> Response:
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        opportunity = find(AcquisitionOpportunity, company=self.tenant_context.company, public_id=data.pop("opportunity_public_id"), message="Acquisition opportunity not found.")
        data.setdefault("event_on", timezone.now())
        try:
            item = create_event(company=self.tenant_context.company, opportunity=opportunity, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "event_type_code": item.event_type_code}, status=201)
