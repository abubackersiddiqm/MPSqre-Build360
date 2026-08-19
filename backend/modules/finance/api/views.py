from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.finance.api.serializers import (
    AdjustmentCreateSerializer,
    BudgetCreateSerializer,
    FinancePolicySerializer,
    InvoiceCreateSerializer,
    PaymentCreateSerializer,
    PeriodCreateSerializer,
    PeriodLockSerializer,
    TransitionSerializer,
    VariationCreateSerializer,
)
from modules.finance.application.services import (
    create_adjustment,
    create_budget,
    create_invoice,
    create_payment,
    create_period,
    create_variation,
    finance_summary,
    lock_period,
    transition_budget,
    transition_invoice,
    transition_payment,
    transition_variation,
)
from modules.finance.models import (
    CommercialAdjustment,
    CommercialLedgerEntry,
    CommercialStage,
    FinancePolicy,
    FinancialPeriod,
    Invoice,
    Payment,
    ProjectBudget,
    Variation,
)
from modules.platform.actors import request_actor
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _stage(stage: CommercialStage) -> dict[str, object]:
    return {
        "public_id": str(stage.public_id),
        "entity_type": stage.entity_type,
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "allowed_next_codes": stage.allowed_next_codes,
    }


def _period(item: FinancialPeriod) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "starts_on": item.starts_on,
        "ends_on": item.ends_on,
        "locked_at": item.locked_at,
        "version": item.version,
    }


def _budget(item: ProjectBudget) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "name": item.name,
        "project": {
            "public_id": str(item.project.public_id),
            "code": item.project.code,
            "name": item.project.name,
        },
        "currency": item.currency,
        "stage": _stage(item.stage),
        "approved_total": str(item.approved_total),
        "forecast_total": str(item.forecast_total),
        "line_count": item.lines.count(),
        "version": item.version,
    }


def _variation(item: Variation) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "variation_number": item.variation_number,
        "title": item.title,
        "variation_type": item.variation_type,
        "project": {
            "public_id": str(item.project.public_id),
            "code": item.project.code,
            "name": item.project.name,
        },
        "stage": _stage(item.stage),
        "currency": item.currency,
        "amount_ex_tax": str(item.amount_ex_tax),
        "tax_amount": str(item.tax_amount),
        "total_amount": str(item.total_amount),
        "version": item.version,
    }


def _invoice(item: Invoice) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "invoice_number": item.invoice_number,
        "invoice_type": item.invoice_type,
        "counterparty_name": item.counterparty_name,
        "project": {
            "public_id": str(item.project.public_id),
            "code": item.project.code,
            "name": item.project.name,
        },
        "period": {"public_id": str(item.period.public_id), "code": item.period.code},
        "stage": _stage(item.stage),
        "currency": item.currency,
        "invoice_date": item.invoice_date,
        "due_date": item.due_date,
        "subtotal": str(item.subtotal),
        "tax_amount": str(item.tax_amount),
        "retention_amount": str(item.retention_amount),
        "total_amount": str(item.total_amount),
        "outstanding_amount": str(item.outstanding_amount),
        "line_count": item.lines.count(),
        "version": item.version,
    }


def _payment(item: Payment) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "payment_number": item.payment_number,
        "payment_type": item.payment_type,
        "invoice": {
            "public_id": str(item.invoice.public_id),
            "invoice_number": item.invoice.invoice_number,
        },
        "period": {"public_id": str(item.period.public_id), "code": item.period.code},
        "stage": _stage(item.stage),
        "currency": item.currency,
        "amount": str(item.amount),
        "paid_on": item.paid_on,
        "reference": item.reference,
        "version": item.version,
    }


class FinanceSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.dashboard.read")
        return Response(finance_summary(self.tenant_context.company))


class StageListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.stage.read")
        items = CommercialStage.objects.filter(
            company=self.tenant_context.company, is_active=True
        ).order_by("entity_type", "sort_order")
        return Response({"items": [_stage(item) for item in items]})


class PeriodListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.period.read")
        return Response(
            {
                "items": [
                    _period(item)
                    for item in FinancialPeriod.objects.filter(company=self.tenant_context.company)[
                        :200
                    ]
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.period.manage")
        serializer = PeriodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_period(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_period(item), status=201)


class PeriodLockView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("finance.period.lock")
        serializer = PeriodLockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = lock_period(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                period_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_period(item))


class BudgetListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.budget.read")
        items = (
            ProjectBudget.objects.select_related("project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [_budget(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.budget.manage")
        serializer = BudgetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_budget(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_budget(item), status=201)


class BudgetTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("finance.budget.approve")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_budget(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                budget_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_budget(item))


class VariationListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.variation.read")
        items = (
            Variation.objects.select_related("project", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-created_at")[:200]
        )
        return Response({"items": [_variation(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.variation.manage")
        serializer = VariationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_variation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_variation(item), status=201)


class VariationTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("finance.variation.approve")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_variation(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                variation_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_variation(item))


class InvoiceListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.invoice.read")
        items = (
            Invoice.objects.select_related("project", "period", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-invoice_date", "-created_at")[:300]
        )
        return Response({"items": [_invoice(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.invoice.manage")
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_invoice(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_invoice(item), status=201)


class InvoiceTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("finance.invoice.approve")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_invoice(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                invoice_public_id=public_id,
                target_code=serializer.validated_data["target_code"],
                expected_version=serializer.validated_data["expected_version"],
                period_public_id=serializer.validated_data.get("period_public_id"),
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_invoice(item))


class PaymentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.payment.read")
        items = (
            Payment.objects.select_related("invoice", "period", "stage")
            .filter(company=self.tenant_context.company)
            .order_by("-paid_on", "-created_at")[:300]
        )
        return Response({"items": [_payment(item) for item in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.payment.manage")
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_payment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_payment(item), status=201)


class PaymentTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("finance.payment.post")
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_payment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                payment_public_id=public_id,
                target_code=serializer.validated_data["target_code"],
                expected_version=serializer.validated_data["expected_version"],
                period_public_id=serializer.validated_data.get("period_public_id"),
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_payment(item))


class FinancePolicyView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.policy.read")
        policy = FinancePolicy.objects.get_or_create(company=self.tenant_context.company)[0]
        return Response(
            {
                "enforce_maker_checker": policy.enforce_maker_checker,
                "allow_backdated_posting": policy.allow_backdated_posting,
                "default_retention_percent": str(policy.default_retention_percent),
                "tax_configuration": policy.tax_configuration,
                "version": policy.version,
            }
        )

    def patch(self, request: Request) -> Response:
        self.tenant_context.require("finance.policy.manage")
        serializer = FinancePolicySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = FinancePolicy.objects.get_or_create(company=self.tenant_context.company)[0]
        for key, value in serializer.validated_data.items():
            setattr(policy, key, value)
        policy.version += 1
        policy.full_clean()
        policy.save()
        return Response(
            {
                "enforce_maker_checker": policy.enforce_maker_checker,
                "allow_backdated_posting": policy.allow_backdated_posting,
                "default_retention_percent": str(policy.default_retention_percent),
                "tax_configuration": policy.tax_configuration,
                "version": policy.version,
            }
        )


class AdjustmentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.adjustment.read")
        items = (
            CommercialAdjustment.objects.select_related("project", "period")
            .filter(company=self.tenant_context.company)
            .order_by("-posted_at")[:300]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "posting_number": item.posting_number,
                        "entry_type": item.entry_type,
                        "project": {
                            "public_id": str(item.project.public_id),
                            "code": item.project.code,
                            "name": item.project.name,
                        },
                        "period": {
                            "public_id": str(item.period.public_id),
                            "code": item.period.code,
                        },
                        "cost_code": item.cost_code,
                        "amount": str(item.amount),
                        "currency": item.currency,
                        "description": item.description,
                        "posted_at": item.posted_at,
                    }
                    for item in items
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("finance.adjustment.post")
        serializer = AdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_adjustment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            {
                "public_id": str(item.public_id),
                "posting_number": item.posting_number,
                "entry_type": item.entry_type,
                "project": {
                    "public_id": str(item.project.public_id),
                    "code": item.project.code,
                    "name": item.project.name,
                },
                "period": {"public_id": str(item.period.public_id), "code": item.period.code},
                "cost_code": item.cost_code,
                "amount": str(item.amount),
                "currency": item.currency,
                "description": item.description,
                "posted_at": item.posted_at,
            },
            status=201,
        )


class LedgerListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("finance.ledger.read")
        items = (
            CommercialLedgerEntry.objects.select_related("project", "period")
            .filter(company=self.tenant_context.company)
            .order_by("-occurred_at")[:500]
        )
        return Response(
            {
                "items": [
                    {
                        "public_id": str(item.public_id),
                        "project": {
                            "public_id": str(item.project.public_id),
                            "code": item.project.code,
                            "name": item.project.name,
                        },
                        "period": {
                            "public_id": str(item.period.public_id),
                            "code": item.period.code,
                        },
                        "entry_type": item.entry_type,
                        "cost_code": item.cost_code,
                        "amount": str(item.amount),
                        "currency": item.currency,
                        "source_type": item.source_type,
                        "source_public_id": str(item.source_public_id),
                        "description": item.description,
                        "occurred_at": item.occurred_at,
                    }
                    for item in items
                ]
            }
        )
