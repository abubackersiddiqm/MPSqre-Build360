from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.salesops.application.selectors import development_sales_overview
from modules.salesops.application.services import (
    create_booking,
    create_buyer,
    create_commission,
    create_handover,
    create_inventory,
    create_milestone,
    create_receipt,
    create_reservation,
    create_unit,
    seed_defaults,
    transition_booking,
    transition_commission,
    transition_handover,
    transition_receipt,
    transition_reservation,
)
from modules.salesops.models import (
    BookingAgreement,
    BrokerCommission,
    BuyerAccount,
    CollectionReceipt,
    CustomerHandover,
    DevelopmentInventory,
    PaymentMilestone,
    SaleableUnit,
    UnitReservation,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    BookingCreateSerializer,
    BuyerCreateSerializer,
    CommissionCreateSerializer,
    HandoverCreateSerializer,
    InventoryCreateSerializer,
    LifecycleTransitionSerializer,
    MilestoneCreateSerializer,
    ReceiptCreateSerializer,
    ReservationCreateSerializer,
    UnitCreateSerializer,
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


class SalesAPIView(TenantScopedAPIView):
    required_permission = "sales.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(SalesAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(development_sales_overview(self.tenant_context.company))


class InventoryCreateView(SalesAPIView):
    required_permission = "sales.inventory"

    def post(self, request: Request) -> Response:
        serializer = InventoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_inventory(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class UnitCreateView(SalesAPIView):
    required_permission = "sales.inventory"

    def post(self, request: Request) -> Response:
        serializer = UnitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        inventory = find(DevelopmentInventory, company=self.tenant_context.company, public_id=data.pop("inventory_public_id"), message="Development inventory not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_unit(company=self.tenant_context.company, inventory=inventory, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class BuyerCreateView(SalesAPIView):
    required_permission = "sales.customer"

    def post(self, request: Request) -> Response:
        serializer = BuyerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_buyer(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "account_code": item.account_code}, status=201)


class ReservationCreateView(SalesAPIView):
    required_permission = "sales.reservation"

    def post(self, request: Request) -> Response:
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        unit = find(SaleableUnit, company=self.tenant_context.company, public_id=data.pop("unit_public_id"), message="Saleable unit not found.")
        buyer = find(BuyerAccount, company=self.tenant_context.company, public_id=data.pop("buyer_public_id"), message="Buyer account not found.")
        if not data.get("reserved_at"):
            data.pop("reserved_at", None)
        if not data.get("expires_at"):
            data.pop("expires_at", None)
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_reservation(company=self.tenant_context.company, unit=unit, buyer=buyer, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "reservation_number": item.reservation_number}, status=201)


class ReservationTransitionView(SalesAPIView):
    required_permission = "sales.reservation"

    def post(self, request: Request, reservation_id: uuid.UUID) -> Response:
        item = find(UnitReservation, company=self.tenant_context.company, public_id=reservation_id, message="Unit reservation not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_reservation(reservation=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class BookingCreateView(SalesAPIView):
    required_permission = "sales.booking"

    def post(self, request: Request) -> Response:
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        unit = find(SaleableUnit, company=self.tenant_context.company, public_id=data.pop("unit_public_id"), message="Saleable unit not found.")
        buyer = find(BuyerAccount, company=self.tenant_context.company, public_id=data.pop("buyer_public_id"), message="Buyer account not found.")
        reservation_id = data.pop("reservation_public_id", None)
        reservation = find(UnitReservation, company=self.tenant_context.company, public_id=reservation_id, message="Unit reservation not found.") if reservation_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_booking(company=self.tenant_context.company, unit=unit, buyer=buyer, reservation=reservation, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "booking_number": item.booking_number}, status=201)


class BookingTransitionView(SalesAPIView):
    required_permission = "sales.approve"

    def post(self, request: Request, booking_id: uuid.UUID) -> Response:
        item = find(BookingAgreement, company=self.tenant_context.company, public_id=booking_id, message="Booking agreement not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_booking(booking=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class MilestoneCreateView(SalesAPIView):
    required_permission = "sales.collection"

    def post(self, request: Request) -> Response:
        serializer = MilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        booking = find(BookingAgreement, company=self.tenant_context.company, public_id=data.pop("booking_public_id"), message="Booking agreement not found.")
        try:
            item = create_milestone(company=self.tenant_context.company, booking=booking, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "milestone_code": item.milestone_code}, status=201)


class ReceiptCreateView(SalesAPIView):
    required_permission = "sales.collection"

    def post(self, request: Request) -> Response:
        serializer = ReceiptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        booking = find(BookingAgreement, company=self.tenant_context.company, public_id=data.pop("booking_public_id"), message="Booking agreement not found.")
        milestone_id = data.pop("milestone_public_id", None)
        milestone = find(PaymentMilestone, company=self.tenant_context.company, public_id=milestone_id, message="Payment milestone not found.") if milestone_id else None
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_receipt(company=self.tenant_context.company, booking=booking, milestone=milestone, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "receipt_number": item.receipt_number}, status=201)


class ReceiptTransitionView(SalesAPIView):
    required_permission = "sales.approve"

    def post(self, request: Request, receipt_id: uuid.UUID) -> Response:
        item = find(CollectionReceipt, company=self.tenant_context.company, public_id=receipt_id, message="Collection receipt not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_receipt(receipt=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class CommissionCreateView(SalesAPIView):
    required_permission = "sales.commission"

    def post(self, request: Request) -> Response:
        serializer = CommissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        booking = find(BookingAgreement, company=self.tenant_context.company, public_id=data.pop("booking_public_id"), message="Booking agreement not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_commission(company=self.tenant_context.company, booking=booking, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "broker_reference": item.broker_reference}, status=201)


class CommissionTransitionView(SalesAPIView):
    required_permission = "sales.approve"

    def post(self, request: Request, commission_id: uuid.UUID) -> Response:
        item = find(BrokerCommission, company=self.tenant_context.company, public_id=commission_id, message="Broker commission not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_commission(commission=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class HandoverCreateView(SalesAPIView):
    required_permission = "sales.handover"

    def post(self, request: Request) -> Response:
        serializer = HandoverCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        booking = find(BookingAgreement, company=self.tenant_context.company, public_id=data.pop("booking_public_id"), message="Booking agreement not found.")
        try:
            item = create_handover(company=self.tenant_context.company, booking=booking, unit=booking.unit, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code}, status=201)


class HandoverTransitionView(SalesAPIView):
    required_permission = "sales.approve"

    def post(self, request: Request, handover_id: uuid.UUID) -> Response:
        item = find(CustomerHandover, company=self.tenant_context.company, public_id=handover_id, message="Customer handover not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_handover(handover=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})
