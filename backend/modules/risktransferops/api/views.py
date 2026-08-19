from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.risktransferops.application.selectors import risk_transfer_overview
from modules.risktransferops.application.services import (
    create_call,
    create_claim,
    create_counterparty,
    create_coverage,
    create_event,
    create_instrument,
    create_loss,
    create_premium,
    create_program,
    seed_defaults,
    transition_call,
    transition_claim,
    transition_counterparty,
    transition_coverage,
    transition_instrument,
    transition_loss,
    transition_premium,
    transition_program,
)
from modules.risktransferops.models import (
    GuaranteeInstrument,
    InstrumentCall,
    InsuranceClaim,
    InsuranceCoverage,
    InsuranceProgram,
    LossEvent,
    PremiumSchedule,
    RiskCounterparty,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    CallCreateSerializer,
    CallTransitionSerializer,
    ClaimCreateSerializer,
    ClaimTransitionSerializer,
    CounterpartyCreateSerializer,
    CoverageCreateSerializer,
    EventCreateSerializer,
    InstrumentCreateSerializer,
    LifecycleTransitionSerializer,
    LossCreateSerializer,
    PremiumCreateSerializer,
    PremiumTransitionSerializer,
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


class RiskTransferAPIView(TenantScopedAPIView):
    required_permission = "risktransfer.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.request.user.public_id


class OverviewView(RiskTransferAPIView):
    def get(self, request: Request) -> Response:
        return Response(risk_transfer_overview(self.tenant_context.company))


class SeedDefaultsView(RiskTransferAPIView):
    required_permission = "risktransfer.manage"

    def post(self, request: Request) -> Response:
        return Response(seed_defaults(self.tenant_context.company))


class CounterpartyCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.counterparty"

    def post(self, request: Request) -> Response:
        serializer = CounterpartyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_counterparty(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "counterparty_code": item.counterparty_code}, status=201)


class CounterpartyTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, counterparty_id: uuid.UUID) -> Response:
        item = find(RiskCounterparty, company=self.tenant_context.company, public_id=counterparty_id, message="Risk counterparty not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_counterparty(counterparty=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class ProgramCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.program"

    def post(self, request: Request) -> Response:
        serializer = ProgramCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_program(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "program_code": item.program_code}, status=201)


class ProgramTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, program_id: uuid.UUID) -> Response:
        item = find(InsuranceProgram, company=self.tenant_context.company, public_id=program_id, message="Insurance program not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_program(program=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class CoverageCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.coverage"

    def post(self, request: Request) -> Response:
        serializer = CoverageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(InsuranceProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Insurance program not found.")
        counterparty = find(RiskCounterparty, company=self.tenant_context.company, public_id=data.pop("counterparty_public_id"), message="Risk counterparty not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_coverage(company=self.tenant_context.company, program=program, counterparty=counterparty, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "policy_number": item.policy_number}, status=201)


class CoverageTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, coverage_id: uuid.UUID) -> Response:
        item = find(InsuranceCoverage, company=self.tenant_context.company, public_id=coverage_id, message="Insurance coverage not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_coverage(coverage=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class PremiumCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.premium"

    def post(self, request: Request) -> Response:
        serializer = PremiumCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        coverage = find(InsuranceCoverage, company=self.tenant_context.company, public_id=data.pop("coverage_public_id"), message="Insurance coverage not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_premium(company=self.tenant_context.company, coverage=coverage, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "installment_number": item.installment_number}, status=201)


class PremiumTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.premium"

    def post(self, request: Request, premium_id: uuid.UUID) -> Response:
        item = find(PremiumSchedule, company=self.tenant_context.company, public_id=premium_id, message="Premium schedule not found.")
        serializer = PremiumTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_premium(premium=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "paid_amount": str(item.paid_amount), "version": item.version})


class LossCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.loss"

    def post(self, request: Request) -> Response:
        serializer = LossCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(InsuranceProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Insurance program not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_loss(company=self.tenant_context.company, program=program, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "loss_number": item.loss_number}, status=201)


class LossTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.loss"

    def post(self, request: Request, loss_id: uuid.UUID) -> Response:
        item = find(LossEvent, company=self.tenant_context.company, public_id=loss_id, message="Loss event not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_loss(loss=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class ClaimCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.claim"

    def post(self, request: Request) -> Response:
        serializer = ClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        loss = find(LossEvent, company=self.tenant_context.company, public_id=data.pop("loss_event_public_id"), message="Loss event not found.")
        coverage = find(InsuranceCoverage, company=self.tenant_context.company, public_id=data.pop("coverage_public_id"), message="Insurance coverage not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_claim(company=self.tenant_context.company, loss_event=loss, coverage=coverage, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "claim_number": item.claim_number}, status=201)


class ClaimTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, claim_id: uuid.UUID) -> Response:
        item = find(InsuranceClaim, company=self.tenant_context.company, public_id=claim_id, message="Insurance claim not found.")
        serializer = ClaimTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_claim(claim=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "recovered_amount": str(item.recovered_amount), "version": item.version})


class InstrumentCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.instrument"

    def post(self, request: Request) -> Response:
        serializer = InstrumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = find(InsuranceProgram, company=self.tenant_context.company, public_id=data.pop("program_public_id"), message="Insurance program not found.")
        counterparty = find(RiskCounterparty, company=self.tenant_context.company, public_id=data.pop("counterparty_public_id"), message="Risk counterparty not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_instrument(company=self.tenant_context.company, program=program, counterparty=counterparty, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "instrument_number": item.instrument_number}, status=201)


class InstrumentTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, instrument_id: uuid.UUID) -> Response:
        item = find(GuaranteeInstrument, company=self.tenant_context.company, public_id=instrument_id, message="Guarantee instrument not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_instrument(instrument=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class CallCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.call"

    def post(self, request: Request) -> Response:
        serializer = CallCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        instrument = find(GuaranteeInstrument, company=self.tenant_context.company, public_id=data.pop("instrument_public_id"), message="Guarantee instrument not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_call(company=self.tenant_context.company, instrument=instrument, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "call_number": item.call_number}, status=201)


class CallTransitionView(RiskTransferAPIView):
    required_permission = "risktransfer.approve"

    def post(self, request: Request, call_id: uuid.UUID) -> Response:
        item = find(InstrumentCall, company=self.tenant_context.company, public_id=call_id, message="Guarantee call not found.")
        serializer = CallTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_call(call=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class EventCreateView(RiskTransferAPIView):
    required_permission = "risktransfer.manage"

    def post(self, request: Request) -> Response:
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program_id = data.pop("program_public_id", None)
        program = find(InsuranceProgram, company=self.tenant_context.company, public_id=program_id, message="Insurance program not found.") if program_id else None
        try:
            item = create_event(company=self.tenant_context.company, program=program, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "event_type_code": item.event_type_code}, status=201)
