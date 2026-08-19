from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.capitalops.application.selectors import capital_overview
from modules.capitalops.application.services import (
    create_commitment,
    create_covenant_test,
    create_debt_facility,
    create_distribution,
    create_drawdown,
    create_event,
    create_investor,
    create_joint_venture,
    create_program,
    seed_defaults,
    transition_commitment,
    transition_covenant_test,
    transition_debt_facility,
    transition_distribution,
    transition_drawdown,
    transition_investor,
    transition_joint_venture,
    transition_program,
)
from modules.capitalops.models import (
    CapitalCommitment,
    CovenantTest,
    DebtFacility,
    DrawdownRequest,
    FundingProgram,
    InvestorDistribution,
    InvestorProfile,
    JointVentureArrangement,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    CommitmentCreateSerializer,
    CovenantCreateSerializer,
    DebtFacilityCreateSerializer,
    DistributionCreateSerializer,
    DistributionTransitionSerializer,
    DrawdownCreateSerializer,
    DrawdownTransitionSerializer,
    EventCreateSerializer,
    InvestorCreateSerializer,
    JointVentureCreateSerializer,
    LifecycleTransitionSerializer,
    ProgramCreateSerializer,
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


class CapitalAPIView(TenantScopedAPIView):
    required_permission = "capital.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(CapitalAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(capital_overview(self.tenant_context.company))


class ProgramCreateView(CapitalAPIView):
    required_permission = "capital.program"

    def post(self, request: Request) -> Response:
        serializer = ProgramCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_program(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "program_code": item.program_code}, status=201)


class ProgramTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, program_id: uuid.UUID) -> Response:
        item = find(FundingProgram, company=self.tenant_context.company, public_id=program_id, message="Funding program not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_program(
                program=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class InvestorCreateView(CapitalAPIView):
    required_permission = "capital.investor"

    def post(self, request: Request) -> Response:
        serializer = InvestorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_investor(
                company=self.tenant_context.company,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "investor_code": item.investor_code}, status=201)


class InvestorTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, investor_id: uuid.UUID) -> Response:
        item = find(InvestorProfile, company=self.tenant_context.company, public_id=investor_id, message="Investor not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_investor(
                investor=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.kyc_status_code, "version": item.version})


class JointVentureCreateView(CapitalAPIView):
    required_permission = "capital.jv"

    def post(self, request: Request) -> Response:
        serializer = JointVentureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        try:
            item = create_joint_venture(
                company=self.tenant_context.company,
                program=program,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "venture_code": item.venture_code}, status=201)


class JointVentureTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, venture_id: uuid.UUID) -> Response:
        item = find(JointVentureArrangement, company=self.tenant_context.company, public_id=venture_id, message="Joint venture not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_joint_venture(
                joint_venture=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class CommitmentCreateView(CapitalAPIView):
    required_permission = "capital.commitment"

    def post(self, request: Request) -> Response:
        serializer = CommitmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        investor_id = data.pop("investor_public_id", None)
        venture_id = data.pop("joint_venture_public_id", None)
        investor = find(InvestorProfile, company=self.tenant_context.company, public_id=investor_id, message="Investor not found.") if investor_id else None
        venture = find(JointVentureArrangement, company=self.tenant_context.company, public_id=venture_id, message="Joint venture not found.") if venture_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_commitment(
                company=self.tenant_context.company,
                program=program,
                investor=investor,
                joint_venture=venture,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "commitment_number": item.commitment_number}, status=201)


class CommitmentTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, commitment_id: uuid.UUID) -> Response:
        item = find(CapitalCommitment, company=self.tenant_context.company, public_id=commitment_id, message="Capital commitment not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_commitment(
                commitment=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class DebtFacilityCreateView(CapitalAPIView):
    required_permission = "capital.facility"

    def post(self, request: Request) -> Response:
        serializer = DebtFacilityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_debt_facility(
                company=self.tenant_context.company,
                program=program,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "facility_code": item.facility_code}, status=201)


class DebtFacilityTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, facility_id: uuid.UUID) -> Response:
        item = find(DebtFacility, company=self.tenant_context.company, public_id=facility_id, message="Debt facility not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_debt_facility(
                facility=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class DrawdownCreateView(CapitalAPIView):
    required_permission = "capital.drawdown"

    def post(self, request: Request) -> Response:
        serializer = DrawdownCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        facility_id = data.pop("debt_facility_public_id", None)
        commitment_id = data.pop("commitment_public_id", None)
        facility = find(DebtFacility, company=self.tenant_context.company, public_id=facility_id, message="Debt facility not found.") if facility_id else None
        commitment = find(CapitalCommitment, company=self.tenant_context.company, public_id=commitment_id, message="Capital commitment not found.") if commitment_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_drawdown(
                company=self.tenant_context.company,
                program=program,
                debt_facility=facility,
                commitment=commitment,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "request_number": item.request_number}, status=201)


class DrawdownTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, drawdown_id: uuid.UUID) -> Response:
        item = find(DrawdownRequest, company=self.tenant_context.company, public_id=drawdown_id, message="Drawdown request not found.")
        serializer = DrawdownTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_drawdown(
                drawdown=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class CovenantCreateView(CapitalAPIView):
    required_permission = "capital.covenant"

    def post(self, request: Request) -> Response:
        serializer = CovenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        facility = find(DebtFacility, company=self.tenant_context.company, public_id=data.pop("debt_facility_public_id"), message="Debt facility not found.")
        try:
            item = create_covenant_test(
                company=self.tenant_context.company,
                facility=facility,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "test_number": item.test_number, "compliant": item.compliant}, status=201)


class CovenantTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, test_id: uuid.UUID) -> Response:
        item = find(CovenantTest, company=self.tenant_context.company, public_id=test_id, message="Covenant test not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_covenant_test(
                test=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class DistributionCreateView(CapitalAPIView):
    required_permission = "capital.distribution"

    def post(self, request: Request) -> Response:
        serializer = DistributionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        investor_id = data.pop("investor_public_id", None)
        venture_id = data.pop("joint_venture_public_id", None)
        investor = find(InvestorProfile, company=self.tenant_context.company, public_id=investor_id, message="Investor not found.") if investor_id else None
        venture = find(JointVentureArrangement, company=self.tenant_context.company, public_id=venture_id, message="Joint venture not found.") if venture_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_distribution(
                company=self.tenant_context.company,
                program=program,
                investor=investor,
                joint_venture=venture,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "distribution_number": item.distribution_number}, status=201)


class DistributionTransitionView(CapitalAPIView):
    required_permission = "capital.approve"

    def post(self, request: Request, distribution_id: uuid.UUID) -> Response:
        item = find(InvestorDistribution, company=self.tenant_context.company, public_id=distribution_id, message="Distribution not found.")
        serializer = DistributionTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_distribution(
                distribution=item,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **serializer.validated_data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class EventCreateView(CapitalAPIView):
    required_permission = "capital.manage"

    def post(self, request: Request) -> Response:
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(FundingProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Funding program not found.")
        try:
            item = create_event(
                company=self.tenant_context.company,
                program=program,
                actor_public_id=self.actor,
                correlation_id=correlation_id(request),
                **data,
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "event_type": item.event_type_code}, status=201)
