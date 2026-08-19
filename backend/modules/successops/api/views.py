from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.platform.actors import request_actor
from modules.successops.api.serializers import (
    AdoptionSnapshotSerializer,
    InvoiceCreateSerializer,
    InvoiceIssueSerializer,
    PaymentCreateSerializer,
    SuccessPlanCreateSerializer,
    SupportTicketCreateSerializer,
    SupportTicketTransitionSerializer,
)
from modules.successops.application.services import (
    create_invoice,
    create_success_plan,
    create_support_ticket,
    customer_users,
    issue_invoice,
    record_adoption_snapshot,
    record_payment,
    successops_portfolio,
    successops_summary,
    transition_support_ticket,
)
from modules.successops.models import (
    AdoptionSnapshot,
    BillingProfile,
    CustomerSuccessAccount,
    PaymentRecord,
    SubscriptionInvoice,
    SuccessPlan,
    SupportSlaPolicy,
    SupportTicket,
)
from modules.tenant.api.base import TenantScopedAPIView


def _validation(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


def _membership(item) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "public_id": str(item.public_id),
        "user_public_id": str(item.user.public_id),
        "display_name": item.user.display_name,
        "email": item.user.email,
    }


def _account(item: CustomerSuccessAccount) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "display_name": item.display_name,
        "segment": item.segment,
        "status": item.status,
        "account_owner": _membership(item.account_owner),
        "customer_since": item.customer_since,
        "renewal_on": item.renewal_on,
        "health_score": item.health_score,
        "risk_level": item.risk_level,
        "desired_outcomes": item.desired_outcomes,
        "risk_summary": item.risk_summary,
        "version": item.version,
    }


def _billing_profile(item: BillingProfile) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "account_public_id": str(item.account.public_id),
        "legal_name": item.legal_name,
        "billing_email": item.billing_email,
        "tax_identifier_masked": item.tax_identifier_masked,
        "currency": item.currency,
        "billing_cycle": item.billing_cycle,
        "payment_terms_days": item.payment_terms_days,
        "status": item.status,
        "version": item.version,
    }


def _invoice(item: SubscriptionInvoice) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "account_public_id": str(item.account.public_id),
        "account_name": item.account.display_name,
        "invoice_number": item.invoice_number,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "issued_on": item.issued_on,
        "due_on": item.due_on,
        "currency": item.currency,
        "subtotal": item.subtotal,
        "tax_amount": item.tax_amount,
        "total_amount": item.total_amount,
        "outstanding_amount": item.outstanding_amount,
        "status": item.status,
        "external_reference": item.external_reference,
        "evidence_sha256": item.evidence_sha256,
        "version": item.version,
    }


def _payment(item: PaymentRecord) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "invoice_public_id": str(item.invoice.public_id),
        "invoice_number": item.invoice.invoice_number,
        "reference": item.reference,
        "amount": item.amount,
        "received_at": item.received_at,
        "status": item.status,
        "evidence_sha256": item.evidence_sha256,
        "version": item.version,
    }


def _sla(item: SupportSlaPolicy) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "code": item.code,
        "severity": item.severity,
        "first_response_minutes": item.first_response_minutes,
        "resolution_minutes": item.resolution_minutes,
        "escalation_minutes": item.escalation_minutes,
        "business_hours_only": item.business_hours_only,
        "is_active": item.is_active,
        "version": item.version,
    }


def _ticket(item: SupportTicket) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "account_public_id": str(item.account.public_id),
        "account_name": item.account.display_name,
        "ticket_number": item.ticket_number,
        "subject": item.subject,
        "description": item.description,
        "category": item.category,
        "severity": item.severity,
        "status": item.status,
        "assigned_membership": _membership(item.assigned_membership),
        "opened_at": item.opened_at,
        "first_responded_at": item.first_responded_at,
        "resolved_at": item.resolved_at,
        "response_due_at": item.response_due_at,
        "resolution_due_at": item.resolution_due_at,
        "escalated_at": item.escalated_at,
        "resolution_summary": item.resolution_summary,
        "version": item.version,
    }


def _plan(item: SuccessPlan) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "account_public_id": str(item.account.public_id),
        "account_name": item.account.display_name,
        "code": item.code,
        "title": item.title,
        "objectives": item.objectives,
        "owner_membership": _membership(item.owner_membership),
        "status": item.status,
        "next_review_on": item.next_review_on,
        "renewal_on": item.renewal_on,
        "health_score": item.health_score,
        "risk_summary": item.risk_summary,
        "version": item.version,
    }


def _adoption(item: AdoptionSnapshot) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "captured_on": item.captured_on,
        "active_users": item.active_users,
        "active_projects": item.active_projects,
        "support_ticket_count": item.support_ticket_count,
        "feature_utilization": item.feature_utilization,
        "adoption_score": item.adoption_score,
        "engagement_score": item.engagement_score,
        "evidence_sha256": item.evidence_sha256,
    }


class SuccessopsSummaryView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.dashboard.read")
        return Response(successops_summary(self.tenant_context.company))


class SuccessopsPortfolioView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.dashboard.read")
        portfolio = successops_portfolio(self.tenant_context.company)
        return Response(
            {
                "summary": portfolio["summary"],
                "current_user_public_id": str(self.tenant_context.principal.user.public_id),
                "memberships": customer_users(self.tenant_context.company),
                "accounts": [_account(item) for item in portfolio["accounts"]],
                "billing_profiles": [
                    _billing_profile(item) for item in portfolio["billing_profiles"]
                ],
                "invoices": [_invoice(item) for item in portfolio["invoices"]],
                "payments": [_payment(item) for item in portfolio["payments"]],
                "sla_policies": [_sla(item) for item in portfolio["sla_policies"]],
                "tickets": [_ticket(item) for item in portfolio["tickets"]],
                "success_plans": [_plan(item) for item in portfolio["success_plans"]],
                "adoption_snapshots": [
                    _adoption(item) for item in portfolio["adoption_snapshots"]
                ],
            }
        )


class SupportTicketListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.support.read")
        values = SupportTicket.objects.filter(
            company=self.tenant_context.company
        ).select_related("account", "assigned_membership", "assigned_membership__user")
        return Response([_ticket(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("success.support.create")
        serializer = SupportTicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_support_ticket(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_ticket(item), status=201)


class SupportTicketTransitionView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("success.support.manage")
        serializer = SupportTicketTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_support_ticket(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                ticket_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_ticket(item))


class InvoiceListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.billing.read")
        values = SubscriptionInvoice.objects.filter(
            company=self.tenant_context.company
        ).select_related("account")
        return Response([_invoice(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("success.billing.manage")
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


class InvoiceIssueView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("success.billing.issue")
        serializer = InvoiceIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = issue_invoice(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                invoice_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_invoice(item))


class PaymentListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.billing.read")
        values = PaymentRecord.objects.filter(
            company=self.tenant_context.company
        ).select_related("invoice")
        return Response([_payment(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("success.billing.payment")
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_payment(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_payment(item), status=201)


class SuccessPlanListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.plan.read")
        values = SuccessPlan.objects.filter(company=self.tenant_context.company).select_related(
            "account", "owner_membership", "owner_membership__user"
        )
        return Response([_plan(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("success.plan.manage")
        serializer = SuccessPlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = create_success_plan(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_plan(item), status=201)


class AdoptionSnapshotListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("success.adoption.read")
        values = AdoptionSnapshot.objects.filter(company=self.tenant_context.company)
        return Response([_adoption(item) for item in values])

    def post(self, request: Request) -> Response:
        self.tenant_context.require("success.adoption.collect")
        serializer = AdoptionSnapshotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = record_adoption_snapshot(
                company=self.tenant_context.company,
                actor=request_actor(request, self.tenant_context),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_adoption(item), status=201)
