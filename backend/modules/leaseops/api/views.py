from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.leaseops.application.selectors import property_lease_overview
from modules.leaseops.application.services import (
    create_case,
    create_charge,
    create_invoice,
    create_lease,
    create_occupancy,
    create_property,
    create_tenant,
    create_unit,
    seed_defaults,
    transition_case,
    transition_invoice,
    transition_lease,
    transition_occupancy,
)
from modules.leaseops.models import (
    LeaseableUnit,
    LeaseAgreement,
    ManagedProperty,
    OccupancyRecord,
    RentInvoice,
    TenantAccount,
    TenantExperienceCase,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    CaseCreateSerializer,
    CaseTransitionSerializer,
    ChargeCreateSerializer,
    InvoiceCreateSerializer,
    InvoiceTransitionSerializer,
    LeaseCreateSerializer,
    LifecycleTransitionSerializer,
    OccupancyCreateSerializer,
    PropertyCreateSerializer,
    TenantCreateSerializer,
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


class LeaseAPIView(TenantScopedAPIView):
    required_permission = "lease.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(LeaseAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        return Response(property_lease_overview(self.tenant_context.company))


class PropertyCreateView(LeaseAPIView):
    required_permission = "lease.property"

    def post(self, request: Request) -> Response:
        serializer = PropertyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_property(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class UnitCreateView(LeaseAPIView):
    required_permission = "lease.unit"

    def post(self, request: Request) -> Response:
        serializer = UnitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        property = find(ManagedProperty, company=self.tenant_context.company, public_id=data.pop("property_public_id"), message="Property not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_unit(company=self.tenant_context.company, property=property, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code}, status=201)


class TenantCreateView(LeaseAPIView):
    required_permission = "lease.tenant"

    def post(self, request: Request) -> Response:
        serializer = TenantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_tenant(company=self.tenant_context.company, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "account_code": item.account_code}, status=201)


class LeaseCreateView(LeaseAPIView):
    required_permission = "lease.agreement"

    def post(self, request: Request) -> Response:
        serializer = LeaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        property = find(ManagedProperty, company=self.tenant_context.company, public_id=data.pop("property_public_id"), message="Property not found.")
        unit = find(LeaseableUnit, company=self.tenant_context.company, public_id=data.pop("unit_public_id"), message="Leaseable unit not found.")
        tenant = find(TenantAccount, company=self.tenant_context.company, public_id=data.pop("tenant_public_id"), message="Tenant account not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_lease(company=self.tenant_context.company, property=property, unit=unit, tenant=tenant, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "lease_number": item.lease_number}, status=201)


class LeaseTransitionView(LeaseAPIView):
    required_permission = "lease.approve"

    def post(self, request: Request, lease_id: uuid.UUID) -> Response:
        item = find(LeaseAgreement, company=self.tenant_context.company, public_id=lease_id, message="Lease agreement not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_lease(lease=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class ChargeCreateView(LeaseAPIView):
    required_permission = "lease.billing"

    def post(self, request: Request) -> Response:
        serializer = ChargeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lease = find(LeaseAgreement, company=self.tenant_context.company, public_id=data.pop("lease_public_id"), message="Lease agreement not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_charge(company=self.tenant_context.company, lease=lease, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "charge_code": item.charge_code}, status=201)


class OccupancyCreateView(LeaseAPIView):
    required_permission = "lease.occupancy"

    def post(self, request: Request) -> Response:
        serializer = OccupancyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lease = find(LeaseAgreement, company=self.tenant_context.company, public_id=data.pop("lease_public_id"), message="Lease agreement not found.")
        try:
            item = create_occupancy(company=self.tenant_context.company, lease=lease, unit=lease.unit, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code}, status=201)


class OccupancyTransitionView(LeaseAPIView):
    required_permission = "lease.occupancy"

    def post(self, request: Request, occupancy_id: uuid.UUID) -> Response:
        item = find(OccupancyRecord, company=self.tenant_context.company, public_id=occupancy_id, message="Occupancy record not found.")
        serializer = LifecycleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_occupancy(occupancy=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class InvoiceCreateView(LeaseAPIView):
    required_permission = "lease.billing"

    def post(self, request: Request) -> Response:
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lease = find(LeaseAgreement, company=self.tenant_context.company, public_id=data.pop("lease_public_id"), message="Lease agreement not found.")
        if not data.get("currency_code"):
            data.pop("currency_code", None)
        try:
            item = create_invoice(company=self.tenant_context.company, lease=lease, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "invoice_number": item.invoice_number}, status=201)


class InvoiceTransitionView(LeaseAPIView):
    required_permission = "lease.approve"

    def post(self, request: Request, invoice_id: uuid.UUID) -> Response:
        item = find(RentInvoice, company=self.tenant_context.company, public_id=invoice_id, message="Rent invoice not found.")
        serializer = InvoiceTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_invoice(invoice=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "paid_amount": str(item.paid_amount), "version": item.version})


class CaseCreateView(LeaseAPIView):
    required_permission = "lease.experience"

    def post(self, request: Request) -> Response:
        serializer = CaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        tenant = find(TenantAccount, company=self.tenant_context.company, public_id=data.pop("tenant_public_id"), message="Tenant account not found.")
        property = find(ManagedProperty, company=self.tenant_context.company, public_id=data.pop("property_public_id"), message="Property not found.")
        unit = None
        unit_id = data.pop("unit_public_id", None)
        if unit_id:
            unit = find(LeaseableUnit, company=self.tenant_context.company, public_id=unit_id, message="Leaseable unit not found.")
        try:
            item = create_case(company=self.tenant_context.company, tenant=tenant, property=property, unit=unit, actor_public_id=self.actor, correlation_id=correlation_id(request), **data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "case_number": item.case_number}, status=201)


class CaseTransitionView(LeaseAPIView):
    required_permission = "lease.experience"

    def post(self, request: Request, case_id: uuid.UUID) -> Response:
        item = find(TenantExperienceCase, company=self.tenant_context.company, public_id=case_id, message="Tenant experience case not found.")
        serializer = CaseTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_case(case=item, actor_public_id=self.actor, correlation_id=correlation_id(request), **serializer.validated_data)
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})
