from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from modules.inventory.application.services import post_movement
from modules.inventory.models import InventoryItem, Warehouse
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RfqVendor,
    VendorQuote,
)
from modules.projects.models import Project
from modules.tenant.models import Company, Membership
from modules.vendor.application.services import initial_stage
from modules.vendor.models import SupplyStage, VendorProfile


def _assert_membership(company: Company, membership_public_id: uuid.UUID) -> None:
    exists = Membership.objects.filter(
        company=company,
        public_id=membership_public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).exists()
    if not exists:
        raise ValidationError("Membership does not belong to this company")


def _record(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _target_stage(
    company: Company,
    entity_type: str,
    code: str,
) -> SupplyStage:
    stage = SupplyStage.objects.filter(
        company=company,
        entity_type=entity_type,
        code=code,
        is_active=True,
    ).first()
    if stage is None:
        raise ValidationError(f"The {entity_type} stage '{code}' is not configured")
    return stage


@transaction.atomic
def create_purchase_request(
    *,
    company: Company,
    actor: RequestActor,
    request_number: str,
    title: str,
    lines: list[dict[str, Any]],
    description: str = "",
    project_public_id: uuid.UUID | None = None,
    required_by_date: Any = None,
    delivery_location: dict[str, Any] | None = None,
    currency: str | None = None,
) -> PurchaseRequest:
    project = None
    if project_public_id:
        project = Project.objects.filter(
            company=company,
            public_id=project_public_id,
        ).first()
        if project is None:
            raise ValidationError("Project was not found")

    _assert_membership(company, actor.membership_public_id)
    if not lines:
        raise ValidationError("At least one purchase request line is required")

    purchase_request = PurchaseRequest(
        company=company,
        request_number=request_number.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        project=project,
        stage=initial_stage(company, SupplyStage.EntityType.PURCHASE_REQUEST),
        requester_membership_public_id=actor.membership_public_id,
        required_by_date=required_by_date,
        delivery_location=delivery_location or {},
        currency=(currency or company.currency).upper(),
    )
    purchase_request.full_clean()
    purchase_request.save()

    estimated_total = Decimal("0")
    for line_number, row in enumerate(lines, 1):
        item = None
        item_public_id = row.get("item_public_id")
        if item_public_id:
            item = InventoryItem.objects.filter(
                company=company,
                public_id=item_public_id,
                is_active=True,
            ).first()
            if item is None:
                raise ValidationError("Inventory item was not found")

        quantity = Decimal(str(row["quantity"]))
        unit_rate = Decimal(str(row.get("estimated_unit_rate", "0")))
        item_code = item.code if item else str(row.get("item_code", "")).strip().upper()
        if not item_code:
            raise ValidationError("Each line requires an inventory item or item code")

        request_line = PurchaseRequestLine(
            company=company,
            request=purchase_request,
            line_number=line_number,
            item=item,
            item_code=item_code,
            description=str(row["description"]).strip(),
            quantity=quantity,
            unit_code=str(row["unit_code"]).strip().lower(),
            estimated_unit_rate=unit_rate,
        )
        request_line.full_clean()
        request_line.save()
        estimated_total += request_line.estimated_total

    purchase_request.estimated_total = estimated_total
    purchase_request.save(update_fields=["estimated_total", "updated_at"])
    _record(
        actor=actor,
        company=company,
        action="procurement.request_created",
        entity_type="purchase_request",
        entity_public_id=purchase_request.public_id,
        version=purchase_request.version,
        payload={
            "request_number": purchase_request.request_number,
            "line_count": len(lines),
            "estimated_total": str(estimated_total),
            "version": purchase_request.version,
        },
    )
    return purchase_request


@transaction.atomic
def transition_request(
    *,
    company: Company,
    actor: RequestActor,
    request_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
) -> PurchaseRequest:
    purchase_request = (
        PurchaseRequest.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=request_public_id)
        .first()
    )
    if purchase_request is None:
        raise ValidationError("Purchase request was not found")
    if purchase_request.version != expected_version:
        raise ValidationError("Purchase request changed; refresh before retrying")
    if target_code not in purchase_request.stage.allowed_next_codes:
        raise ValidationError("Requested transition is not permitted")

    target = _target_stage(
        company,
        SupplyStage.EntityType.PURCHASE_REQUEST,
        target_code,
    )
    purchase_request.stage = target
    purchase_request.version += 1
    purchase_request.full_clean()
    purchase_request.save()
    _record(
        actor=actor,
        company=company,
        action="procurement.request_transitioned",
        entity_type="purchase_request",
        entity_public_id=purchase_request.public_id,
        version=purchase_request.version,
        payload={"stage": target.code, "version": purchase_request.version},
    )
    return purchase_request


@transaction.atomic
def create_rfq(
    *,
    company: Company,
    actor: RequestActor,
    purchase_request_public_id: uuid.UUID,
    rfq_number: str,
    title: str,
    vendor_public_ids: list[uuid.UUID],
    close_at: Any = None,
) -> RequestForQuotation:
    purchase_request = (
        PurchaseRequest.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=purchase_request_public_id)
        .first()
    )
    if purchase_request is None:
        raise ValidationError("Purchase request was not found")
    if purchase_request.stage.code != "approved":
        raise ValidationError("Only an approved purchase request can create an RFQ")
    if not vendor_public_ids:
        raise ValidationError("At least one vendor must be invited")

    unique_vendor_ids = set(vendor_public_ids)
    vendors = list(
        VendorProfile.objects.select_related("stage").filter(
            company=company,
            public_id__in=unique_vendor_ids,
            stage__code="qualified",
            retired_at__isnull=True,
        )
    )
    if len(vendors) != len(unique_vendor_ids):
        raise ValidationError("Every invited vendor must exist and be qualified")

    rfq = RequestForQuotation(
        company=company,
        purchase_request=purchase_request,
        rfq_number=rfq_number.strip().upper(),
        title=title.strip(),
        stage=initial_stage(company, SupplyStage.EntityType.RFQ),
        close_at=close_at,
    )
    rfq.full_clean()
    rfq.save()
    now = timezone.now()
    RfqVendor.objects.bulk_create(
        [
            RfqVendor(
                company=company,
                rfq=rfq,
                vendor=vendor,
                invited_at=now,
            )
            for vendor in vendors
        ]
    )

    purchase_request.stage = _target_stage(
        company,
        SupplyStage.EntityType.PURCHASE_REQUEST,
        "rfq_created",
    )
    purchase_request.version += 1
    purchase_request.save(update_fields=["stage", "version", "updated_at"])
    _record(
        actor=actor,
        company=company,
        action="procurement.rfq_created",
        entity_type="rfq",
        entity_public_id=rfq.public_id,
        version=rfq.version,
        payload={
            "rfq_number": rfq.rfq_number,
            "vendor_count": len(vendors),
            "version": rfq.version,
        },
    )
    return rfq


@transaction.atomic
def transition_rfq(
    *,
    company: Company,
    actor: RequestActor,
    rfq_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
) -> RequestForQuotation:
    rfq = (
        RequestForQuotation.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=rfq_public_id)
        .first()
    )
    if rfq is None:
        raise ValidationError("RFQ was not found")
    if rfq.version != expected_version:
        raise ValidationError("RFQ changed; refresh before retrying")
    if target_code not in rfq.stage.allowed_next_codes:
        raise ValidationError("Requested RFQ transition is not permitted")

    target = _target_stage(company, SupplyStage.EntityType.RFQ, target_code)
    rfq.stage = target
    rfq.version += 1
    if target.code == "issued" and rfq.issue_at is None:
        rfq.issue_at = timezone.now()
    rfq.full_clean()
    rfq.save()
    _record(
        actor=actor,
        company=company,
        action="procurement.rfq_transitioned",
        entity_type="rfq",
        entity_public_id=rfq.public_id,
        version=rfq.version,
        payload={"stage": target.code, "version": rfq.version},
    )
    return rfq


@transaction.atomic
def submit_quote(
    *,
    company: Company,
    actor: RequestActor,
    rfq_public_id: uuid.UUID,
    vendor_public_id: uuid.UUID,
    quote_number: str,
    subtotal: Decimal,
    tax_amount: Decimal = Decimal("0"),
    freight_amount: Decimal = Decimal("0"),
    valid_until: Any = None,
) -> VendorQuote:
    rfq = (
        RequestForQuotation.objects.select_related("purchase_request", "stage")
        .filter(company=company, public_id=rfq_public_id)
        .first()
    )
    vendor = VendorProfile.objects.filter(
        company=company,
        public_id=vendor_public_id,
    ).first()
    if rfq is None or vendor is None:
        raise ValidationError("RFQ or vendor was not found")
    if rfq.stage.code != "issued":
        raise ValidationError("Quotes can be submitted only while the RFQ is issued")
    if rfq.close_at and rfq.close_at <= timezone.now():
        raise ValidationError("The RFQ is closed for quote submission")
    invited = RfqVendor.objects.filter(
        company=company,
        rfq=rfq,
        vendor=vendor,
    ).exists()
    if not invited:
        raise ValidationError("Vendor was not invited to this RFQ")

    total = subtotal + tax_amount + freight_amount
    quote = VendorQuote(
        company=company,
        rfq=rfq,
        vendor=vendor,
        quote_number=quote_number.strip().upper(),
        stage=initial_stage(company, SupplyStage.EntityType.QUOTE),
        currency=rfq.purchase_request.currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        freight_amount=freight_amount,
        total_amount=total,
        valid_until=valid_until,
        submitted_at=timezone.now(),
    )
    quote.full_clean()
    quote.save()
    _record(
        actor=actor,
        company=company,
        action="procurement.quote_submitted",
        entity_type="vendor_quote",
        entity_public_id=quote.public_id,
        version=quote.version,
        payload={
            "quote_number": quote.quote_number,
            "total_amount": str(total),
            "version": quote.version,
        },
    )
    return quote


@transaction.atomic
def award_quote(
    *,
    company: Company,
    actor: RequestActor,
    quote_public_id: uuid.UUID,
    po_number: str,
) -> PurchaseOrder:
    quote = (
        VendorQuote.objects.select_for_update()
        .select_related("rfq__purchase_request", "rfq__stage", "vendor", "stage")
        .filter(company=company, public_id=quote_public_id)
        .first()
    )
    if quote is None:
        raise ValidationError("Quote was not found")
    existing = PurchaseOrder.objects.filter(
        company=company,
        awarded_quote=quote,
    ).first()
    if existing:
        return existing
    if quote.rfq.stage.code != "closed":
        raise ValidationError("The RFQ must be closed before awarding a quote")
    if quote.stage.code != "submitted":
        raise ValidationError("Only a submitted quote can be awarded")

    purchase_order = PurchaseOrder(
        company=company,
        po_number=po_number.strip().upper(),
        purchase_request=quote.rfq.purchase_request,
        rfq=quote.rfq,
        awarded_quote=quote,
        vendor=quote.vendor,
        stage=initial_stage(company, SupplyStage.EntityType.PURCHASE_ORDER),
        currency=quote.currency,
        total_amount=quote.total_amount,
    )
    purchase_order.full_clean()
    purchase_order.save()

    request_lines = list(
        quote.rfq.purchase_request.lines.select_related("item").order_by("line_number")
    )
    estimated_total = sum(
        (line.estimated_total for line in request_lines),
        Decimal("0"),
    )
    for request_line in request_lines:
        unit_rate = request_line.estimated_unit_rate
        if estimated_total and request_line.quantity:
            allocated_line_value = (
                quote.subtotal * request_line.estimated_total / estimated_total
            )
            unit_rate = allocated_line_value / request_line.quantity
        PurchaseOrderLine.objects.create(
            company=company,
            purchase_order=purchase_order,
            request_line=request_line,
            line_number=request_line.line_number,
            item=request_line.item,
            description=request_line.description,
            quantity_ordered=request_line.quantity,
            unit_code=request_line.unit_code,
            unit_rate=unit_rate,
        )

    accepted_stage = _target_stage(
        company,
        SupplyStage.EntityType.QUOTE,
        "accepted",
    )
    rejected_stage = _target_stage(
        company,
        SupplyStage.EntityType.QUOTE,
        "rejected",
    )
    VendorQuote.objects.filter(
        company=company,
        rfq=quote.rfq,
        stage__code="submitted",
    ).exclude(pk=quote.pk).update(stage=rejected_stage, version=models.F("version") + 1)
    quote.stage = accepted_stage
    quote.version += 1
    quote.save(update_fields=["stage", "version", "updated_at"])

    rfq = quote.rfq
    rfq.stage = _target_stage(company, SupplyStage.EntityType.RFQ, "awarded")
    rfq.version += 1
    rfq.save(update_fields=["stage", "version", "updated_at"])

    purchase_request = rfq.purchase_request
    purchase_request.stage = _target_stage(
        company,
        SupplyStage.EntityType.PURCHASE_REQUEST,
        "ordered",
    )
    purchase_request.version += 1
    purchase_request.save(update_fields=["stage", "version", "updated_at"])

    _record(
        actor=actor,
        company=company,
        action="procurement.quote_awarded",
        entity_type="purchase_order",
        entity_public_id=purchase_order.public_id,
        version=purchase_order.version,
        payload={
            "po_number": purchase_order.po_number,
            "vendor": quote.vendor.code,
            "total_amount": str(purchase_order.total_amount),
            "version": purchase_order.version,
        },
    )
    return purchase_order


@transaction.atomic
def transition_purchase_order(
    *,
    company: Company,
    actor: RequestActor,
    purchase_order_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
) -> PurchaseOrder:
    purchase_order = (
        PurchaseOrder.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=purchase_order_public_id)
        .first()
    )
    if purchase_order is None:
        raise ValidationError("Purchase order was not found")
    if purchase_order.version != expected_version:
        raise ValidationError("Purchase order changed; refresh before retrying")
    if target_code not in purchase_order.stage.allowed_next_codes:
        raise ValidationError("Requested purchase-order transition is not permitted")

    target = _target_stage(
        company,
        SupplyStage.EntityType.PURCHASE_ORDER,
        target_code,
    )
    purchase_order.stage = target
    purchase_order.version += 1
    if target.code == "issued" and purchase_order.issued_at is None:
        purchase_order.issued_at = timezone.now()
    purchase_order.full_clean()
    purchase_order.save()
    _record(
        actor=actor,
        company=company,
        action="procurement.po_transitioned",
        entity_type="purchase_order",
        entity_public_id=purchase_order.public_id,
        version=purchase_order.version,
        payload={"stage": target.code, "version": purchase_order.version},
    )
    return purchase_order


@transaction.atomic
def create_receipt(
    *,
    company: Company,
    actor: RequestActor,
    purchase_order_public_id: uuid.UUID,
    warehouse_public_id: uuid.UUID,
    receipt_number: str,
    lines: list[dict[str, Any]],
) -> GoodsReceipt:
    purchase_order = (
        PurchaseOrder.objects.select_related("stage")
        .filter(company=company, public_id=purchase_order_public_id)
        .first()
    )
    warehouse = Warehouse.objects.filter(
        company=company,
        public_id=warehouse_public_id,
        is_active=True,
    ).first()
    if purchase_order is None or warehouse is None:
        raise ValidationError("Purchase order or warehouse was not found")
    if purchase_order.stage.code not in {"issued", "partially_received"}:
        raise ValidationError("Receipts require an issued purchase order")
    if not lines:
        raise ValidationError("At least one receipt line is required")

    receipt = GoodsReceipt(
        company=company,
        receipt_number=receipt_number.strip().upper(),
        purchase_order=purchase_order,
        warehouse=warehouse,
        stage=initial_stage(company, SupplyStage.EntityType.RECEIPT),
        received_at=timezone.now(),
        received_by_membership_public_id=actor.membership_public_id,
    )
    receipt.full_clean()
    receipt.save()

    seen_po_lines: set[uuid.UUID] = set()
    for line_number, row in enumerate(lines, 1):
        po_line_public_id = row["purchase_order_line_public_id"]
        if po_line_public_id in seen_po_lines:
            raise ValidationError("A purchase-order line can appear only once per receipt")
        seen_po_lines.add(po_line_public_id)

        purchase_order_line = PurchaseOrderLine.objects.filter(
            company=company,
            purchase_order=purchase_order,
            public_id=po_line_public_id,
        ).first()
        if purchase_order_line is None:
            raise ValidationError("Purchase-order line was not found")

        quantity_received = Decimal(str(row["quantity_received"]))
        quantity_accepted = Decimal(
            str(row.get("quantity_accepted", quantity_received))
        )
        quantity_rejected = quantity_received - quantity_accepted
        receipt_line = GoodsReceiptLine(
            company=company,
            receipt=receipt,
            purchase_order_line=purchase_order_line,
            line_number=line_number,
            quantity_received=quantity_received,
            quantity_accepted=quantity_accepted,
            quantity_rejected=quantity_rejected,
            notes=str(row.get("notes", "")).strip(),
        )
        receipt_line.full_clean()
        receipt_line.save()

    _record(
        actor=actor,
        company=company,
        action="procurement.receipt_created",
        entity_type="goods_receipt",
        entity_public_id=receipt.public_id,
        version=receipt.version,
        payload={
            "receipt_number": receipt.receipt_number,
            "line_count": len(lines),
            "version": receipt.version,
        },
    )
    return receipt


@transaction.atomic
def post_receipt(
    *,
    company: Company,
    actor: RequestActor,
    receipt_public_id: uuid.UUID,
    expected_version: int,
) -> GoodsReceipt:
    receipt = (
        GoodsReceipt.objects.select_for_update()
        .select_related("warehouse", "stage", "purchase_order__stage")
        .filter(company=company, public_id=receipt_public_id)
        .first()
    )
    if receipt is None:
        raise ValidationError("Goods receipt was not found")
    if receipt.version != expected_version:
        raise ValidationError("Goods receipt changed; refresh before retrying")
    if receipt.posted_at:
        return receipt

    for receipt_line in receipt.lines.select_related("purchase_order_line__item"):
        purchase_order_line = PurchaseOrderLine.objects.select_for_update().get(
            pk=receipt_line.purchase_order_line_id
        )
        projected_received = (
            purchase_order_line.quantity_received + receipt_line.quantity_accepted
        )
        if projected_received > purchase_order_line.quantity_ordered:
            raise ValidationError("Receipt exceeds ordered quantity")

        purchase_order_line.quantity_received = projected_received
        purchase_order_line.save(
            update_fields=["quantity_received", "updated_at"]
        )
        if purchase_order_line.item and receipt_line.quantity_accepted > 0:
            post_movement(
                company=company,
                actor=actor,
                item_public_id=purchase_order_line.item.public_id,
                warehouse_public_id=receipt.warehouse.public_id,
                movement_type="receipt",
                quantity=receipt_line.quantity_accepted,
                unit_cost=purchase_order_line.unit_rate,
                source_type="goods_receipt",
                source_public_id=receipt.public_id,
                source_line_key=str(receipt_line.public_id),
                reason_code="po_receipt",
            )

    receipt.stage = _target_stage(
        company,
        SupplyStage.EntityType.RECEIPT,
        "posted",
    )
    receipt.posted_at = timezone.now()
    receipt.version += 1
    receipt.save()

    purchase_order = receipt.purchase_order
    all_received = not purchase_order.lines.filter(
        quantity_received__lt=models.F("quantity_ordered")
    ).exists()
    target_po_code = "received" if all_received else "partially_received"
    purchase_order.stage = _target_stage(
        company,
        SupplyStage.EntityType.PURCHASE_ORDER,
        target_po_code,
    )
    purchase_order.version += 1
    purchase_order.save(update_fields=["stage", "version", "updated_at"])

    _record(
        actor=actor,
        company=company,
        action="procurement.receipt_posted",
        entity_type="goods_receipt",
        entity_public_id=receipt.public_id,
        version=receipt.version,
        payload={
            "receipt_number": receipt.receipt_number,
            "purchase_order_stage": target_po_code,
            "version": receipt.version,
        },
    )
    return receipt
