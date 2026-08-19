from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.inventory.api.serializers import (
    ItemCreateSerializer,
    MovementCreateSerializer,
    WarehouseCreateSerializer,
)
from modules.inventory.application.services import create_item, create_warehouse, post_movement
from modules.inventory.models import InventoryItem, StockBalance, StockLedgerEntry, Warehouse
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _item(item: InventoryItem) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "category_code": item.category_code,
        "base_unit_code": item.base_unit_code,
        "track_inventory": item.track_inventory,
        "is_active": item.is_active,
        "version": item.version,
    }


def _warehouse(item: Warehouse) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "project_public_id": str(item.project.public_id) if item.project else None,
        "location": item.location,
        "is_active": item.is_active,
        "version": item.version,
    }


def _balance(item: StockBalance) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "item": _item(item.item),
        "warehouse": _warehouse(item.warehouse),
        "quantity_on_hand": str(item.quantity_on_hand),
        "quantity_reserved": str(item.quantity_reserved),
        "available_quantity": str(item.quantity_on_hand - item.quantity_reserved),
        "average_unit_cost": str(item.average_unit_cost),
        "stock_value": str(item.quantity_on_hand * item.average_unit_cost),
        "version": item.version,
    }


class InventorySummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("inventory.dashboard.read")
        company = self.tenant_context.company
        balances = StockBalance.objects.filter(company=company)
        stock_value = sum(
            (row.quantity_on_hand * row.average_unit_cost for row in balances), Decimal("0")
        )
        return Response(
            {
                "items": InventoryItem.objects.filter(company=company, is_active=True).count(),
                "warehouses": Warehouse.objects.filter(company=company, is_active=True).count(),
                "stock_positions": balances.count(),
                "negative_positions": balances.filter(quantity_on_hand__lt=0).count(),
                "stock_value": str(stock_value),
                "currency": company.currency,
            }
        )


class ItemListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("inventory.item.read")
        return Response(
            {
                "items": [
                    _item(x)
                    for x in InventoryItem.objects.filter(
                        company=self.tenant_context.company
                    ).order_by("name")[:200]
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("inventory.item.manage")
        s = ItemCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            item = create_item(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_item(item), status=201)


class WarehouseListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("inventory.warehouse.read")
        return Response(
            {
                "items": [
                    _warehouse(x)
                    for x in Warehouse.objects.select_related("project")
                    .filter(company=self.tenant_context.company)
                    .order_by("name")[:200]
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("inventory.warehouse.manage")
        s = WarehouseCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            item = create_warehouse(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_warehouse(item), status=201)


class BalanceListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("inventory.stock.read")
        qs = (
            StockBalance.objects.select_related("item", "warehouse", "warehouse__project")
            .filter(company=self.tenant_context.company)
            .order_by("warehouse__name", "item__name")[:500]
        )
        return Response({"items": [_balance(x) for x in qs]})


class MovementCreateView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("inventory.movement.post")
        s = MovementCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            entry = post_movement(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **s.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(entry.public_id),
                "movement_type": entry.movement_type,
                "quantity": str(entry.quantity),
                "balance_after": str(entry.balance_after),
            },
            status=201,
        )


class LedgerListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("inventory.ledger.read")
        qs = (
            StockLedgerEntry.objects.select_related("item", "warehouse")
            .filter(company=self.tenant_context.company)
            .order_by("-occurred_at")[:500]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(x.public_id),
                        "item_code": x.item.code,
                        "warehouse_code": x.warehouse.code,
                        "movement_type": x.movement_type,
                        "quantity": str(x.quantity),
                        "unit_cost": str(x.unit_cost),
                        "balance_after": str(x.balance_after),
                        "source_type": x.source_type,
                        "occurred_at": x.occurred_at,
                    }
                    for x in qs
                ]
            }
        )
