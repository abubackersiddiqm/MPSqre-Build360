from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.identity.models import User
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
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
from modules.tenant.models import Company, Membership


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
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
            reason_code=reason_code[:100],
            before=before or {},
            after=after or {},
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            correlation_id=actor.request_id,
            company_public_id=company.public_id,
            payload=payload,
        )
    )


def _sha256_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def successops_summary(company: Company) -> dict[str, Any]:
    today = timezone.localdate()
    invoices = SubscriptionInvoice.objects.filter(company=company)
    tickets = SupportTicket.objects.filter(company=company)
    accounts = CustomerSuccessAccount.objects.filter(company=company)
    open_statuses = [
        SupportTicket.Status.OPEN,
        SupportTicket.Status.TRIAGE,
        SupportTicket.Status.IN_PROGRESS,
        SupportTicket.Status.WAITING_CUSTOMER,
    ]
    latest_adoption = AdoptionSnapshot.objects.filter(company=company).first()
    outstanding = invoices.exclude(
        status__in=[SubscriptionInvoice.Status.PAID, SubscriptionInvoice.Status.VOID]
    ).aggregate(total=Sum("outstanding_amount"))["total"] or Decimal("0")
    return {
        "accounts": accounts.count(),
        "active_accounts": accounts.filter(status=CustomerSuccessAccount.Status.ACTIVE).count(),
        "at_risk_accounts": accounts.filter(status=CustomerSuccessAccount.Status.AT_RISK).count(),
        "average_health_score": round(
            sum(accounts.values_list("health_score", flat=True)) / accounts.count(),
            1,
        ) if accounts.exists() else 0,
        "open_tickets": tickets.filter(status__in=open_statuses).count(),
        "sla_breaches": tickets.filter(
            status__in=open_statuses,
            resolution_due_at__lt=timezone.now(),
        ).count(),
        "outstanding_invoices": invoices.exclude(
            status__in=[SubscriptionInvoice.Status.PAID, SubscriptionInvoice.Status.VOID]
        ).count(),
        "overdue_invoices": invoices.filter(
            due_on__lt=today,
            outstanding_amount__gt=0,
        ).exclude(status=SubscriptionInvoice.Status.VOID).count(),
        "outstanding_amount": outstanding,
        "currency": company.currency,
        "adoption_score": latest_adoption.adoption_score if latest_adoption else 0,
        "engagement_score": latest_adoption.engagement_score if latest_adoption else 0,
    }


def successops_portfolio(company: Company) -> dict[str, Any]:
    return {
        "summary": successops_summary(company),
        "accounts": CustomerSuccessAccount.objects.filter(company=company).select_related(
            "account_owner", "account_owner__user"
        ),
        "billing_profiles": BillingProfile.objects.filter(company=company).select_related(
            "account"
        ),
        "invoices": SubscriptionInvoice.objects.filter(company=company).select_related(
            "account"
        )[:100],
        "payments": PaymentRecord.objects.filter(company=company).select_related(
            "invoice"
        )[:100],
        "sla_policies": SupportSlaPolicy.objects.filter(company=company, is_active=True),
        "tickets": SupportTicket.objects.filter(company=company).select_related(
            "account", "assigned_membership", "assigned_membership__user"
        )[:100],
        "success_plans": SuccessPlan.objects.filter(company=company).select_related(
            "account", "owner_membership", "owner_membership__user"
        ),
        "adoption_snapshots": AdoptionSnapshot.objects.filter(company=company)[:30],
    }


def _membership(company: Company, public_id: uuid.UUID | None) -> Membership | None:
    if public_id is None:
        return None
    item = Membership.objects.filter(
        company=company,
        public_id=public_id,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).first()
    if item is None:
        raise ValidationError("Active membership was not found")
    return item


@transaction.atomic
def create_support_ticket(
    *,
    company: Company,
    actor: RequestActor,
    account_public_id: uuid.UUID,
    subject: str,
    description: str,
    category: str,
    severity: str,
    assigned_membership_public_id: uuid.UUID | None = None,
) -> SupportTicket:
    account = CustomerSuccessAccount.objects.filter(
        company=company,
        public_id=account_public_id,
    ).first()
    if account is None:
        raise ValidationError("Customer success account was not found")
    sla = SupportSlaPolicy.objects.filter(
        company=company,
        severity=severity,
        is_active=True,
    ).first()
    if sla is None:
        raise ValidationError("An active SLA policy was not found for this severity")
    assigned = _membership(company, assigned_membership_public_id)
    now = timezone.now()
    sequence = SupportTicket.objects.filter(company=company).count() + 1
    item = SupportTicket(
        company=company,
        account=account,
        ticket_number=f"SUP-{now:%Y%m%d}-{sequence:05d}",
        subject=subject.strip(),
        description=description.strip(),
        category=category.strip().lower() or "general",
        severity=severity,
        requester_user_public_id=actor.user_public_id,
        assigned_membership=assigned,
        response_due_at=now + timedelta(minutes=sla.first_response_minutes),
        resolution_due_at=now + timedelta(minutes=sla.resolution_minutes),
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.ticket.created",
        entity_type="support_ticket",
        entity_public_id=item.public_id,
        after={"ticket_number": item.ticket_number, "severity": item.severity},
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.ticket.created",
        aggregate_type="support_ticket",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"ticket_number": item.ticket_number, "severity": item.severity},
    )
    return item


_ALLOWED_TICKET_TRANSITIONS = {
    SupportTicket.Status.OPEN: {SupportTicket.Status.TRIAGE, SupportTicket.Status.CLOSED},
    SupportTicket.Status.TRIAGE: {SupportTicket.Status.IN_PROGRESS, SupportTicket.Status.WAITING_CUSTOMER},
    SupportTicket.Status.IN_PROGRESS: {SupportTicket.Status.WAITING_CUSTOMER, SupportTicket.Status.RESOLVED},
    SupportTicket.Status.WAITING_CUSTOMER: {SupportTicket.Status.IN_PROGRESS, SupportTicket.Status.RESOLVED},
    SupportTicket.Status.RESOLVED: {SupportTicket.Status.IN_PROGRESS, SupportTicket.Status.CLOSED},
    SupportTicket.Status.CLOSED: set(),
}


@transaction.atomic
def transition_support_ticket(
    *,
    company: Company,
    actor: RequestActor,
    ticket_public_id: uuid.UUID,
    target_status: str,
    expected_version: int,
    resolution_summary: str = "",
    assigned_membership_public_id: uuid.UUID | None = None,
    reason: str = "",
) -> SupportTicket:
    item = SupportTicket.objects.select_for_update().filter(
        company=company,
        public_id=ticket_public_id,
    ).first()
    if item is None:
        raise ValidationError("Support ticket was not found")
    if item.version != expected_version:
        raise ValidationError("Support ticket changed; refresh before retrying")
    if target_status not in _ALLOWED_TICKET_TRANSITIONS[item.status]:
        raise ValidationError(f"Transition from {item.status} to {target_status} is not allowed")
    before = {"status": item.status, "version": item.version}
    now = timezone.now()
    if assigned_membership_public_id is not None:
        item.assigned_membership = _membership(company, assigned_membership_public_id)
    if target_status in [SupportTicket.Status.TRIAGE, SupportTicket.Status.IN_PROGRESS] and not item.first_responded_at:
        item.first_responded_at = now
    if target_status in [SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]:
        item.resolved_at = item.resolved_at or now
        item.resolution_summary = resolution_summary.strip() or item.resolution_summary
    item.status = target_status
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.ticket.transitioned",
        entity_type="support_ticket",
        entity_public_id=item.public_id,
        before=before,
        after={"status": item.status, "version": item.version},
        reason_code=reason,
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.ticket.transitioned",
        aggregate_type="support_ticket",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"ticket_number": item.ticket_number, "status": item.status},
    )
    return item


@transaction.atomic
def create_invoice(
    *,
    company: Company,
    actor: RequestActor,
    account_public_id: uuid.UUID,
    invoice_number: str,
    period_start: date,
    period_end: date,
    currency: str,
    subtotal: Decimal,
    tax_amount: Decimal,
    external_reference: str = "",
) -> SubscriptionInvoice:
    account = CustomerSuccessAccount.objects.filter(
        company=company,
        public_id=account_public_id,
    ).first()
    if account is None:
        raise ValidationError("Customer success account was not found")
    total = subtotal + tax_amount
    item = SubscriptionInvoice(
        company=company,
        account=account,
        invoice_number=invoice_number.strip().upper(),
        period_start=period_start,
        period_end=period_end,
        currency=currency.strip().upper(),
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total,
        outstanding_amount=total,
        external_reference=external_reference.strip(),
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.invoice.created",
        entity_type="subscription_invoice",
        entity_public_id=item.public_id,
        after={"invoice_number": item.invoice_number, "total_amount": str(item.total_amount)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.invoice.created",
        aggregate_type="subscription_invoice",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"invoice_number": item.invoice_number, "currency": item.currency},
    )
    return item


@transaction.atomic
def issue_invoice(
    *,
    company: Company,
    actor: RequestActor,
    invoice_public_id: uuid.UUID,
    issued_on: date,
    due_on: date,
    expected_version: int,
) -> SubscriptionInvoice:
    item = SubscriptionInvoice.objects.select_for_update().filter(
        company=company,
        public_id=invoice_public_id,
    ).first()
    if item is None:
        raise ValidationError("Subscription invoice was not found")
    if item.version != expected_version:
        raise ValidationError("Invoice changed; refresh before retrying")
    if item.status != SubscriptionInvoice.Status.DRAFT:
        raise ValidationError("Only draft invoices can be issued")
    item.issued_on = issued_on
    item.due_on = due_on
    item.status = SubscriptionInvoice.Status.ISSUED
    item.evidence_sha256 = _sha256_payload(
        {
            "invoice_number": item.invoice_number,
            "issued_on": issued_on,
            "due_on": due_on,
            "total_amount": item.total_amount,
        }
    )
    item.version += 1
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.invoice.issued",
        entity_type="subscription_invoice",
        entity_public_id=item.public_id,
        after={"status": item.status, "due_on": str(item.due_on)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.invoice.issued",
        aggregate_type="subscription_invoice",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"invoice_number": item.invoice_number, "due_on": str(item.due_on)},
    )
    return item


@transaction.atomic
def record_payment(
    *,
    company: Company,
    actor: RequestActor,
    invoice_public_id: uuid.UUID,
    reference: str,
    amount: Decimal,
    received_at: datetime,
) -> PaymentRecord:
    invoice = SubscriptionInvoice.objects.select_for_update().filter(
        company=company,
        public_id=invoice_public_id,
    ).first()
    if invoice is None:
        raise ValidationError("Subscription invoice was not found")
    if invoice.status in [SubscriptionInvoice.Status.DRAFT, SubscriptionInvoice.Status.VOID]:
        raise ValidationError("Payments cannot be posted to draft or void invoices")
    if amount > invoice.outstanding_amount:
        raise ValidationError("Payment cannot exceed the outstanding invoice amount")
    evidence = _sha256_payload(
        {
            "invoice": invoice.invoice_number,
            "reference": reference,
            "amount": amount,
            "received_at": received_at,
        }
    )
    payment = PaymentRecord(
        company=company,
        invoice=invoice,
        reference=reference.strip().upper(),
        amount=amount,
        received_at=received_at,
        status=PaymentRecord.Status.VERIFIED,
        evidence_sha256=evidence,
    )
    payment.full_clean()
    payment.save()
    invoice.outstanding_amount -= amount
    invoice.status = (
        SubscriptionInvoice.Status.PAID
        if invoice.outstanding_amount == 0
        else SubscriptionInvoice.Status.PARTIALLY_PAID
    )
    invoice.version += 1
    invoice.full_clean()
    invoice.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.payment.recorded",
        entity_type="payment_record",
        entity_public_id=payment.public_id,
        after={"reference": payment.reference, "amount": str(payment.amount)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.payment.recorded",
        aggregate_type="subscription_invoice",
        aggregate_public_id=invoice.public_id,
        aggregate_version=invoice.version,
        payload={"invoice_number": invoice.invoice_number, "status": invoice.status},
    )
    return payment


@transaction.atomic
def create_success_plan(
    *,
    company: Company,
    actor: RequestActor,
    account_public_id: uuid.UUID,
    code: str,
    title: str,
    objectives: list[Any],
    owner_membership_public_id: uuid.UUID,
    next_review_on: date | None = None,
    renewal_on: date | None = None,
) -> SuccessPlan:
    account = CustomerSuccessAccount.objects.filter(
        company=company,
        public_id=account_public_id,
    ).first()
    if account is None:
        raise ValidationError("Customer success account was not found")
    owner = _membership(company, owner_membership_public_id)
    assert owner is not None
    item = SuccessPlan(
        company=company,
        account=account,
        code=code.strip().upper(),
        title=title.strip(),
        objectives=objectives,
        owner_membership=owner,
        next_review_on=next_review_on,
        renewal_on=renewal_on,
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.plan.created",
        entity_type="success_plan",
        entity_public_id=item.public_id,
        after={"code": item.code, "status": item.status},
    )
    _event(
        actor=actor,
        company=company,
        event_type="successops.plan.created",
        aggregate_type="success_plan",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"code": item.code, "status": item.status},
    )
    return item


@transaction.atomic
def record_adoption_snapshot(
    *,
    company: Company,
    actor: RequestActor,
    captured_on: date,
    active_users: int,
    active_projects: int,
    support_ticket_count: int,
    feature_utilization: dict[str, Any],
    adoption_score: int,
    engagement_score: int,
) -> AdoptionSnapshot:
    payload = {
        "company": str(company.public_id),
        "captured_on": captured_on,
        "active_users": active_users,
        "active_projects": active_projects,
        "support_ticket_count": support_ticket_count,
        "feature_utilization": feature_utilization,
        "adoption_score": adoption_score,
        "engagement_score": engagement_score,
    }
    item, created = AdoptionSnapshot.objects.update_or_create(
        company=company,
        captured_on=captured_on,
        defaults={
            "active_users": active_users,
            "active_projects": active_projects,
            "support_ticket_count": support_ticket_count,
            "feature_utilization": feature_utilization,
            "adoption_score": adoption_score,
            "engagement_score": engagement_score,
            "evidence_sha256": _sha256_payload(payload),
        },
    )
    item.full_clean()
    item.save()
    _audit(
        actor=actor,
        company=company,
        action="successops.adoption.recorded",
        entity_type="adoption_snapshot",
        entity_public_id=item.public_id,
        after={"captured_on": str(captured_on), "adoption_score": adoption_score},
        reason_code="created" if created else "refreshed",
    )
    return item


def customer_users(company: Company) -> list[dict[str, str]]:
    memberships = Membership.objects.filter(
        company=company,
        suspended_at__isnull=True,
        terminated_at__isnull=True,
    ).select_related("user")
    return [
        {
            "membership_public_id": str(item.public_id),
            "user_public_id": str(item.user.public_id),
            "email": item.user.email,
            "display_name": item.user.display_name,
        }
        for item in memberships
        if isinstance(item.user, User)
    ]
