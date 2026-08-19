from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.procurement.api.serializers import (
    AwardQuoteSerializer,
    PurchaseRequestCreateSerializer,
    QuoteCreateSerializer,
    ReceiptCreateSerializer,
    ReceiptPostSerializer,
    RequestTransitionSerializer,
    RfqCreateSerializer,
)
from modules.procurement.application.services import (
    award_quote,
    create_purchase_request,
    create_receipt,
    create_rfq,
    post_receipt,
    submit_quote,
    transition_purchase_order,
    transition_request,
    transition_rfq,
)
from modules.procurement.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseRequest,
    RequestForQuotation,
    VendorQuote,
)
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _stage(s):
    return {
        "public_id": str(s.public_id),
        "code": s.code,
        "name": s.name,
        "outcome": s.outcome,
        "allowed_next_codes": s.allowed_next_codes,
    }


def _request(x):
    return {
        "public_id": str(x.public_id),
        "request_number": x.request_number,
        "title": x.title,
        "description": x.description,
        "project_public_id": str(x.project.public_id) if x.project else None,
        "stage": _stage(x.stage),
        "required_by_date": x.required_by_date,
        "currency": x.currency,
        "estimated_total": str(x.estimated_total),
        "line_count": x.lines.count(),
        "version": x.version,
        "created_at": x.created_at,
    }


def _rfq(x):
    return {
        "public_id": str(x.public_id),
        "rfq_number": x.rfq_number,
        "title": x.title,
        "purchase_request_public_id": str(x.purchase_request.public_id),
        "stage": _stage(x.stage),
        "vendor_count": x.vendor_invitations.count(),
        "quote_count": x.quotes.count(),
        "close_at": x.close_at,
        "version": x.version,
    }


def _quote(x):
    return {
        "public_id": str(x.public_id),
        "quote_number": x.quote_number,
        "rfq_public_id": str(x.rfq.public_id),
        "vendor": {
            "public_id": str(x.vendor.public_id),
            "code": x.vendor.code,
            "display_name": x.vendor.display_name,
        },
        "stage": _stage(x.stage),
        "currency": x.currency,
        "subtotal": str(x.subtotal),
        "tax_amount": str(x.tax_amount),
        "freight_amount": str(x.freight_amount),
        "total_amount": str(x.total_amount),
        "valid_until": x.valid_until,
        "version": x.version,
    }


def _po(x):
    return {
        "public_id": str(x.public_id),
        "po_number": x.po_number,
        "vendor": {
            "public_id": str(x.vendor.public_id),
            "code": x.vendor.code,
            "display_name": x.vendor.display_name,
        },
        "stage": _stage(x.stage),
        "currency": x.currency,
        "total_amount": str(x.total_amount),
        "line_count": x.lines.count(),
        "version": x.version,
        "created_at": x.created_at,
    }


def _receipt(x):
    return {
        "public_id": str(x.public_id),
        "receipt_number": x.receipt_number,
        "purchase_order_public_id": str(x.purchase_order.public_id),
        "po_number": x.purchase_order.po_number,
        "warehouse_public_id": str(x.warehouse.public_id),
        "warehouse_name": x.warehouse.name,
        "stage": _stage(x.stage),
        "received_at": x.received_at,
        "posted_at": x.posted_at,
        "line_count": x.lines.count(),
        "version": x.version,
    }


class ProcurementSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.dashboard.read")
        c = self.tenant_context.company
        prs = PurchaseRequest.objects.filter(company=c)
        rfqs = RequestForQuotation.objects.filter(company=c)
        pos = PurchaseOrder.objects.filter(company=c)
        receipts = GoodsReceipt.objects.filter(company=c)
        return Response(
            {
                "purchase_requests": prs.count(),
                "open_rfqs": rfqs.exclude(stage__outcome__in=["complete", "cancelled"]).count(),
                "quotes": VendorQuote.objects.filter(company=c).count(),
                "purchase_orders": pos.count(),
                "po_value": str(pos.aggregate(v=Sum("total_amount"))["v"] or Decimal("0")),
                "unposted_receipts": receipts.filter(posted_at__isnull=True).count(),
                "currency": c.currency,
            }
        )


class RequestListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.request.read")
        qs = (
            PurchaseRequest.objects.select_related("project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [_request(x) for x in qs]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("procurement.request.manage")
        s = PurchaseRequestCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = create_purchase_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_request(obj), status=201)


class RequestTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("procurement.request.transition")
        s = RequestTransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = transition_request(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                request_public_id=public_id,
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_request(obj))


class RfqListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.rfq.read")
        qs = (
            RequestForQuotation.objects.select_related("purchase_request", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [_rfq(x) for x in qs]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("procurement.rfq.manage")
        s = RfqCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = create_rfq(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_rfq(obj), status=201)


class RfqTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("procurement.rfq.manage")
        serializer = RequestTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            obj = transition_rfq(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                rfq_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_rfq(obj))


class QuoteListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.quote.read")
        qs = (
            VendorQuote.objects.select_related("rfq", "vendor", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("rfq_id", "total_amount")[:300]
        )
        return Response({"items": [_quote(x) for x in qs]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("procurement.quote.manage")
        s = QuoteCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = submit_quote(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_quote(obj), status=201)


class QuoteAwardView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("procurement.award.decide")
        s = AwardQuoteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = award_quote(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                quote_public_id=public_id,
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_po(obj), status=201)


class PurchaseOrderListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.po.read")
        qs = (
            PurchaseOrder.objects.select_related("vendor", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [_po(x) for x in qs]})


class PurchaseOrderTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("procurement.po.manage")
        serializer = RequestTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            obj = transition_purchase_order(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                purchase_order_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_po(obj))


class ReceiptListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("procurement.receipt.read")
        qs = (
            GoodsReceipt.objects.select_related("purchase_order", "warehouse", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-received_at")[:200]
        )
        return Response({"items": [_receipt(x) for x in qs]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("procurement.receipt.manage")
        s = ReceiptCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = create_receipt(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_receipt(obj), status=201)


class ReceiptPostView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("procurement.receipt.post")
        s = ReceiptPostSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            obj = post_receipt(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                receipt_public_id=public_id,
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_receipt(obj))
