from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.inventory.models import (
    InventoryItem,
    StockBalance,
    StockLedgerEntry,
    Warehouse,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.tenant.models import Company


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


@transaction.atomic
def create_item(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    base_unit_code: str,
    category_code: str = "",
    description: str = "",
    track_inventory: bool = True,
) -> InventoryItem:
    item = InventoryItem(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        base_unit_code=base_unit_code.strip().lower(),
        category_code=category_code.strip().lower(),
        description=description.strip(),
        track_inventory=track_inventory,
    )
    item.full_clean()
    item.save()
    _record(
        actor=actor,
        company=company,
        action="inventory.item_created",
        entity_type="inventory_item",
        entity_public_id=item.public_id,
        version=item.version,
        payload={"code": item.code, "version": item.version},
    )
    return item


@transaction.atomic
def create_warehouse(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    project_public_id: uuid.UUID | None = None,
    location: dict[str, Any] | None = None,
) -> Warehouse:
    project = None
    if project_public_id:
        project = Project.objects.filter(
            company=company,
            public_id=project_public_id,
        ).first()
        if project is None:
            raise ValidationError("Project was not found")

    warehouse = Warehouse(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        project=project,
        location=location or {},
    )
    warehouse.full_clean()
    warehouse.save()
    _record(
        actor=actor,
        company=company,
        action="inventory.warehouse_created",
        entity_type="warehouse",
        entity_public_id=warehouse.public_id,
        version=warehouse.version,
        payload={"code": warehouse.code, "version": warehouse.version},
    )
    return warehouse


@transaction.atomic
def post_movement(
    *,
    company: Company,
    actor: RequestActor,
    item_public_id: uuid.UUID,
    warehouse_public_id: uuid.UUID,
    movement_type: str,
    quantity: Decimal,
    source_type: str,
    source_public_id: uuid.UUID,
    unit_cost: Decimal = Decimal("0"),
    source_line_key: str = "",
    reason_code: str = "",
) -> StockLedgerEntry:
    item = InventoryItem.objects.filter(
        company=company,
        public_id=item_public_id,
        is_active=True,
    ).first()
    warehouse = Warehouse.objects.filter(
        company=company,
        public_id=warehouse_public_id,
        is_active=True,
    ).first()
    if item is None or warehouse is None:
        raise ValidationError("Inventory item or warehouse was not found")
    if movement_type not in StockLedgerEntry.MovementType.values:
        raise ValidationError("Movement type is invalid")
    if quantity == 0:
        raise ValidationError("Movement quantity cannot be zero")
    if unit_cost < 0:
        raise ValidationError("Unit cost cannot be negative")

    existing = StockLedgerEntry.objects.filter(
        company=company,
        source_type=source_type.strip(),
        source_public_id=source_public_id,
        source_line_key=source_line_key.strip(),
    ).first()
    if existing:
        return existing

    balance, _ = StockBalance.objects.select_for_update().get_or_create(
        company=company,
        item=item,
        warehouse=warehouse,
    )
    current_quantity = balance.quantity_on_hand
    new_quantity = current_quantity + quantity
    if new_quantity < 0:
        raise ValidationError("Inventory movement would create negative stock")

    if quantity > 0:
        total_value = (
            current_quantity * balance.average_unit_cost + quantity * unit_cost
        )
        balance.average_unit_cost = (
            total_value / new_quantity if new_quantity else Decimal("0")
        )
    balance.quantity_on_hand = new_quantity
    balance.version += 1
    balance.full_clean()
    balance.save()

    entry = StockLedgerEntry(
        company=company,
        item=item,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        balance_after=new_quantity,
        source_type=source_type.strip(),
        source_public_id=source_public_id,
        source_line_key=source_line_key.strip(),
        occurred_at=timezone.now(),
        posted_by_public_id=actor.user_public_id,
        reason_code=reason_code.strip(),
    )
    entry.full_clean()
    entry.save()
    _record(
        actor=actor,
        company=company,
        action="inventory.movement_posted",
        entity_type="stock_ledger",
        entity_public_id=entry.public_id,
        version=balance.version,
        payload={
            "item": item.code,
            "warehouse": warehouse.code,
            "quantity": str(quantity),
            "balance_after": str(new_quantity),
            "version": balance.version,
        },
    )
    return entry
