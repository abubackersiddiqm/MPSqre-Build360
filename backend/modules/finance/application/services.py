from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from modules.finance.application.stages import assert_transition, initial_stage, resolve_stage
from modules.finance.models import (
    BudgetLine,
    CommercialAdjustment,
    CommercialLedgerEntry,
    CommercialStage,
    FinancePolicy,
    FinancialPeriod,
    Invoice,
    InvoiceLine,
    Payment,
    ProjectBudget,
    Variation,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.models import Project
from modules.tenant.models import Company

MONEY = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _audit(
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    *,
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
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
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
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _project(company: Company, public_id: uuid.UUID) -> Project:
    project = Project.objects.filter(company=company, public_id=public_id).first()
    if project is None:
        raise ValidationError("Project was not found")
    return project


def _period(company: Company, public_id: uuid.UUID) -> FinancialPeriod:
    period = FinancialPeriod.objects.filter(company=company, public_id=public_id).first()
    if period is None:
        raise ValidationError("Financial period was not found")
    return period


def _assert_period_open(period: FinancialPeriod) -> None:
    if period.locked_at is not None:
        raise ValidationError("Financial period is locked")


def _policy(company: Company) -> FinancePolicy:
    return FinancePolicy.objects.get_or_create(company=company)[0]


def _assert_checker(
    company: Company, maker_public_id: uuid.UUID, actor_public_id: uuid.UUID
) -> None:
    if _policy(company).enforce_maker_checker and maker_public_id == actor_public_id:
        raise ValidationError("Maker-checker policy requires a different approver")


def _ledger(
    *,
    company: Company,
    project: Project,
    period: FinancialPeriod,
    entry_type: str,
    amount: Decimal,
    currency: str,
    source_type: str,
    source_public_id: uuid.UUID,
    source_line_key: str,
    actor: RequestActor,
    description: str = "",
    reversal_of: CommercialLedgerEntry | None = None,
) -> CommercialLedgerEntry:
    _assert_period_open(period)
    entry = CommercialLedgerEntry(
        company=company,
        project=project,
        period=period,
        entry_type=entry_type,
        amount=_money(amount),
        currency=currency,
        source_type=source_type,
        source_public_id=source_public_id,
        source_line_key=source_line_key,
        occurred_at=timezone.now(),
        posted_by_public_id=actor.user_public_id,
        description=description,
        reversal_of=reversal_of,
    )
    entry.full_clean()
    try:
        entry.save()
    except IntegrityError as exc:
        raise ValidationError("This financial source fact has already been posted") from exc
    return entry


@transaction.atomic
def create_period(
    *, company: Company, actor: RequestActor, code: str, name: str, starts_on: Any, ends_on: Any
) -> FinancialPeriod:
    period = FinancialPeriod(
        company=company,
        code=code.strip().upper(),
        name=name.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
    )
    period.full_clean()
    period.save()
    _audit(
        actor,
        company,
        "finance.period.created",
        "financial_period",
        period.public_id,
        after={"code": period.code},
    )
    return period


@transaction.atomic
def lock_period(
    *,
    company: Company,
    actor: RequestActor,
    period_public_id: uuid.UUID,
    expected_version: int,
    reason: str,
) -> FinancialPeriod:
    period = (
        FinancialPeriod.objects.select_for_update()
        .filter(company=company, public_id=period_public_id)
        .first()
    )
    if period is None:
        raise ValidationError("Financial period was not found")
    if period.version != expected_version:
        raise ValidationError("Financial period changed; refresh before retrying")
    if period.locked_at is not None:
        return period
    period.locked_at = timezone.now()
    period.locked_by_public_id = actor.user_public_id
    period.lock_reason = reason.strip()
    period.version += 1
    period.save()
    _audit(
        actor,
        company,
        "finance.period.locked",
        "financial_period",
        period.public_id,
        after={"code": period.code, "version": period.version},
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "finance.period.locked",
        "financial_period",
        period.public_id,
        period.version,
        {"code": period.code},
    )
    return period


@transaction.atomic
def create_budget(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    code: str,
    name: str,
    currency: str | None,
    lines: list[dict[str, Any]],
) -> ProjectBudget:
    project = _project(company, project_public_id)
    budget = ProjectBudget(
        company=company,
        project=project,
        code=code.strip().upper(),
        name=name.strip(),
        currency=(currency or company.currency).upper(),
        stage=initial_stage(company, CommercialStage.EntityType.BUDGET),
        created_by_public_id=actor.user_public_id,
    )
    budget.full_clean()
    budget.save()
    approved = Decimal("0")
    forecast = Decimal("0")
    for raw in lines:
        line = BudgetLine(
            company=company,
            budget=budget,
            cost_code=str(raw["cost_code"]).strip().upper(),
            description=str(raw["description"]).strip(),
            approved_amount=_money(raw.get("approved_amount", Decimal("0"))),
            committed_amount=_money(raw.get("committed_amount", Decimal("0"))),
            actual_amount=_money(raw.get("actual_amount", Decimal("0"))),
            accrued_amount=_money(raw.get("accrued_amount", Decimal("0"))),
            forecast_amount=_money(
                raw.get("forecast_amount", raw.get("approved_amount", Decimal("0")))
            ),
        )
        line.full_clean()
        line.save()
        approved += line.approved_amount
        forecast += line.forecast_amount
    budget.approved_total = _money(approved)
    budget.forecast_total = _money(forecast)
    budget.save(update_fields=["approved_total", "forecast_total", "updated_at"])
    _audit(
        actor,
        company,
        "finance.budget.created",
        "project_budget",
        budget.public_id,
        after={
            "code": budget.code,
            "total": str(budget.approved_total),
            "stage": budget.stage.code,
        },
    )
    _event(
        actor,
        company,
        "finance.budget.created",
        "project_budget",
        budget.public_id,
        budget.version,
        {"project_public_id": str(project.public_id), "total": str(budget.approved_total)},
    )
    return budget


@transaction.atomic
def transition_budget(
    *,
    company: Company,
    actor: RequestActor,
    budget_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
    period_public_id: uuid.UUID | None = None,
    reason: str = "",
) -> ProjectBudget:
    budget = (
        ProjectBudget.objects.select_for_update()
        .select_related("stage", "project")
        .filter(company=company, public_id=budget_public_id)
        .first()
    )
    if budget is None:
        raise ValidationError("Budget was not found")
    if budget.version != expected_version:
        raise ValidationError("Budget changed; refresh before retrying")
    target = resolve_stage(company, CommercialStage.EntityType.BUDGET, target_code)
    assert_transition(budget.stage, target)
    before = {"stage": budget.stage.code, "version": budget.version}
    if target.outcome == CommercialStage.Outcome.APPROVED:
        _assert_checker(company, budget.created_by_public_id, actor.user_public_id)
        if period_public_id is None:
            raise ValidationError("Financial period is required when approving a budget")
        period = _period(company, period_public_id)
        _assert_period_open(period)
        for line in budget.lines.all():
            if line.approved_amount:
                _ledger(
                    company=company,
                    project=budget.project,
                    period=period,
                    entry_type=CommercialLedgerEntry.EntryType.BUDGET,
                    amount=line.approved_amount,
                    currency=budget.currency,
                    source_type="project_budget",
                    source_public_id=budget.public_id,
                    source_line_key=line.cost_code,
                    actor=actor,
                    description=line.description,
                )
        budget.approved_by_public_id = actor.user_public_id
        budget.approved_at = timezone.now()
    budget.stage = target
    budget.version += 1
    budget.full_clean()
    budget.save()
    _audit(
        actor,
        company,
        "finance.budget.transitioned",
        "project_budget",
        budget.public_id,
        before=before,
        after={"stage": target.code, "version": budget.version},
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "finance.budget.transitioned",
        "project_budget",
        budget.public_id,
        budget.version,
        {"from": before["stage"], "to": target.code},
    )
    return budget


@transaction.atomic
def create_variation(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    variation_number: str,
    title: str,
    variation_type: str,
    currency: str | None,
    amount_ex_tax: Decimal,
    tax_amount: Decimal = Decimal("0"),
    reason: str = "",
) -> Variation:
    project = _project(company, project_public_id)
    amount = _money(amount_ex_tax)
    tax = _money(tax_amount)
    variation = Variation(
        company=company,
        project=project,
        variation_number=variation_number.strip().upper(),
        title=title.strip(),
        variation_type=variation_type,
        stage=initial_stage(company, CommercialStage.EntityType.VARIATION),
        currency=(currency or company.currency).upper(),
        amount_ex_tax=amount,
        tax_amount=tax,
        total_amount=_money(amount + tax),
        reason=reason.strip(),
        created_by_public_id=actor.user_public_id,
    )
    variation.full_clean()
    variation.save()
    _audit(
        actor,
        company,
        "finance.variation.created",
        "variation",
        variation.public_id,
        after={"number": variation.variation_number, "total": str(variation.total_amount)},
    )
    _event(
        actor,
        company,
        "finance.variation.created",
        "variation",
        variation.public_id,
        variation.version,
        {"project_public_id": str(project.public_id), "total": str(variation.total_amount)},
    )
    return variation


@transaction.atomic
def transition_variation(
    *,
    company: Company,
    actor: RequestActor,
    variation_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
    period_public_id: uuid.UUID | None = None,
    reason: str = "",
) -> Variation:
    variation = (
        Variation.objects.select_for_update()
        .select_related("stage", "project")
        .filter(company=company, public_id=variation_public_id)
        .first()
    )
    if variation is None:
        raise ValidationError("Variation was not found")
    if variation.version != expected_version:
        raise ValidationError("Variation changed; refresh before retrying")
    target = resolve_stage(company, CommercialStage.EntityType.VARIATION, target_code)
    assert_transition(variation.stage, target)
    before = variation.stage.code
    if target.outcome == CommercialStage.Outcome.APPROVED:
        _assert_checker(company, variation.created_by_public_id, actor.user_public_id)
        if period_public_id is None:
            raise ValidationError("Financial period is required when approving a variation")
        period = _period(company, period_public_id)
        _ledger(
            company=company,
            project=variation.project,
            period=period,
            entry_type=CommercialLedgerEntry.EntryType.VARIATION,
            amount=variation.total_amount,
            currency=variation.currency,
            source_type="variation",
            source_public_id=variation.public_id,
            source_line_key="approved",
            actor=actor,
            description=variation.title,
        )
        variation.approved_by_public_id = actor.user_public_id
        variation.approved_at = timezone.now()
    variation.stage = target
    variation.version += 1
    variation.full_clean()
    variation.save()
    _audit(
        actor,
        company,
        "finance.variation.transitioned",
        "variation",
        variation.public_id,
        before={"stage": before},
        after={"stage": target.code, "version": variation.version},
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "finance.variation.transitioned",
        "variation",
        variation.public_id,
        variation.version,
        {"from": before, "to": target.code},
    )
    return variation


@transaction.atomic
def create_invoice(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    period_public_id: uuid.UUID,
    invoice_number: str,
    invoice_type: str,
    counterparty_name: str,
    counterparty_reference: str,
    currency: str | None,
    invoice_date: Any,
    due_date: Any,
    retention_amount: Decimal,
    lines: list[dict[str, Any]],
) -> Invoice:
    project = _project(company, project_public_id)
    period = _period(company, period_public_id)
    _assert_period_open(period)
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(lines, 1):
        quantity = _money(raw["quantity"])
        unit_rate = _money(raw["unit_rate"])
        tax_rate = _money(raw.get("tax_rate_percent", Decimal("0")))
        amount = _money(quantity * unit_rate)
        tax = _money(amount * tax_rate / Decimal("100"))
        total = _money(amount + tax)
        normalized.append(
            {
                **raw,
                "line_number": index,
                "quantity": quantity,
                "unit_rate": unit_rate,
                "tax_rate_percent": tax_rate,
                "amount": amount,
                "tax_amount": tax,
                "total_amount": total,
            }
        )
        subtotal += amount
        tax_total += tax
    total_amount = _money(subtotal + tax_total)
    retention = _money(retention_amount)
    invoice = Invoice(
        company=company,
        project=project,
        period=period,
        invoice_number=invoice_number.strip().upper(),
        invoice_type=invoice_type,
        counterparty_name=counterparty_name.strip(),
        counterparty_reference=counterparty_reference.strip(),
        stage=initial_stage(company, CommercialStage.EntityType.INVOICE),
        currency=(currency or company.currency).upper(),
        invoice_date=invoice_date,
        due_date=due_date,
        subtotal=_money(subtotal),
        tax_amount=_money(tax_total),
        retention_amount=retention,
        total_amount=total_amount,
        outstanding_amount=_money(total_amount - retention),
        created_by_public_id=actor.user_public_id,
    )
    invoice.full_clean()
    invoice.save()
    for row in normalized:
        line = InvoiceLine(
            company=company,
            invoice=invoice,
            line_number=row["line_number"],
            cost_code=str(row["cost_code"]).strip().upper(),
            description=str(row["description"]).strip(),
            quantity=row["quantity"],
            unit_rate=row["unit_rate"],
            tax_rate_percent=row["tax_rate_percent"],
            amount=row["amount"],
            tax_amount=row["tax_amount"],
            total_amount=row["total_amount"],
        )
        line.full_clean()
        line.save()
    _audit(
        actor,
        company,
        "finance.invoice.created",
        "invoice",
        invoice.public_id,
        after={
            "number": invoice.invoice_number,
            "total": str(invoice.total_amount),
            "type": invoice.invoice_type,
        },
    )
    _event(
        actor,
        company,
        "finance.invoice.created",
        "invoice",
        invoice.public_id,
        invoice.version,
        {
            "project_public_id": str(project.public_id),
            "total": str(invoice.total_amount),
            "type": invoice.invoice_type,
        },
    )
    return invoice


@transaction.atomic
def transition_invoice(
    *,
    company: Company,
    actor: RequestActor,
    invoice_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
    period_public_id: uuid.UUID | None = None,
    reason: str = "",
) -> Invoice:
    invoice = (
        Invoice.objects.select_for_update()
        .select_related("stage", "project", "period")
        .filter(company=company, public_id=invoice_public_id)
        .first()
    )
    if invoice is None:
        raise ValidationError("Invoice was not found")
    if invoice.version != expected_version:
        raise ValidationError("Invoice changed; refresh before retrying")
    target = resolve_stage(company, CommercialStage.EntityType.INVOICE, target_code)
    assert_transition(invoice.stage, target)
    before = invoice.stage.code
    if target.outcome in {CommercialStage.Outcome.APPROVED, CommercialStage.Outcome.POSTED}:
        _assert_checker(company, invoice.created_by_public_id, actor.user_public_id)
    if target.outcome == CommercialStage.Outcome.APPROVED:
        invoice.approved_by_public_id = actor.user_public_id
        invoice.approved_at = timezone.now()
    if target.outcome == CommercialStage.Outcome.POSTED:
        _assert_period_open(invoice.period)
        sign = Decimal("1") if invoice.invoice_type == Invoice.InvoiceType.VENDOR else Decimal("-1")
        for line in invoice.lines.all():
            _ledger(
                company=company,
                project=invoice.project,
                period=invoice.period,
                entry_type=CommercialLedgerEntry.EntryType.INVOICE,
                amount=sign * line.total_amount,
                currency=invoice.currency,
                source_type="invoice",
                source_public_id=invoice.public_id,
                source_line_key=str(line.line_number),
                actor=actor,
                description=line.description,
            )
        if invoice.retention_amount:
            _ledger(
                company=company,
                project=invoice.project,
                period=invoice.period,
                entry_type=CommercialLedgerEntry.EntryType.RETENTION,
                amount=sign * invoice.retention_amount,
                currency=invoice.currency,
                source_type="invoice",
                source_public_id=invoice.public_id,
                source_line_key="retention",
                actor=actor,
                description="Retention withheld",
            )
        invoice.posted_at = timezone.now()
    if target.outcome == CommercialStage.Outcome.PAID and invoice.outstanding_amount != 0:
        raise ValidationError("Invoice cannot be marked paid while an outstanding balance remains")
    if target.outcome == CommercialStage.Outcome.REVERSED:
        if invoice.posted_at is None or invoice.reversed_at is not None:
            raise ValidationError("Only a posted, unreversed invoice can be reversed")
        reversal_period = _period(company, period_public_id) if period_public_id else invoice.period
        _assert_period_open(reversal_period)
        originals = CommercialLedgerEntry.objects.filter(
            company=company, source_type="invoice", source_public_id=invoice.public_id
        )
        if not originals.exists():
            raise ValidationError("Invoice posting facts were not found")
        for original in originals:
            _ledger(
                company=company,
                project=invoice.project,
                period=reversal_period,
                entry_type=CommercialLedgerEntry.EntryType.REVERSAL,
                amount=-original.amount,
                currency=invoice.currency,
                source_type="invoice_reversal",
                source_public_id=invoice.public_id,
                source_line_key=str(original.public_id),
                actor=actor,
                description=f"Reversal of {original.description}",
                reversal_of=original,
            )
        invoice.outstanding_amount = Decimal("0")
        invoice.reversed_at = timezone.now()
    invoice.stage = target
    invoice.version += 1
    invoice.full_clean()
    invoice.save()
    _audit(
        actor,
        company,
        "finance.invoice.transitioned",
        "invoice",
        invoice.public_id,
        before={"stage": before},
        after={"stage": target.code, "version": invoice.version},
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "finance.invoice.transitioned",
        "invoice",
        invoice.public_id,
        invoice.version,
        {"from": before, "to": target.code},
    )
    return invoice


@transaction.atomic
def create_payment(
    *,
    company: Company,
    actor: RequestActor,
    invoice_public_id: uuid.UUID,
    period_public_id: uuid.UUID,
    payment_number: str,
    payment_type: str,
    amount: Decimal,
    paid_on: Any,
    reference: str = "",
) -> Payment:
    invoice = (
        Invoice.objects.select_related("project")
        .filter(company=company, public_id=invoice_public_id)
        .first()
    )
    if invoice is None:
        raise ValidationError("Invoice was not found")
    period = _period(company, period_public_id)
    _assert_period_open(period)
    value = _money(amount)
    if payment_type == Payment.PaymentType.STANDARD and value > invoice.outstanding_amount:
        raise ValidationError("Payment cannot exceed the invoice outstanding amount")
    if payment_type == Payment.PaymentType.RETENTION_RELEASE and value > invoice.retention_amount:
        raise ValidationError("Retention release cannot exceed retained value")
    payment = Payment(
        company=company,
        invoice=invoice,
        period=period,
        payment_number=payment_number.strip().upper(),
        payment_type=payment_type,
        stage=initial_stage(company, CommercialStage.EntityType.PAYMENT),
        currency=invoice.currency,
        amount=value,
        paid_on=paid_on,
        reference=reference.strip(),
        created_by_public_id=actor.user_public_id,
    )
    payment.full_clean()
    payment.save()
    _audit(
        actor,
        company,
        "finance.payment.created",
        "payment",
        payment.public_id,
        after={"number": payment.payment_number, "amount": str(payment.amount)},
    )
    return payment


@transaction.atomic
def transition_payment(
    *,
    company: Company,
    actor: RequestActor,
    payment_public_id: uuid.UUID,
    target_code: str,
    expected_version: int,
    period_public_id: uuid.UUID | None = None,
    reason: str = "",
) -> Payment:
    payment = (
        Payment.objects.select_for_update()
        .select_related("stage", "invoice__project", "period")
        .filter(company=company, public_id=payment_public_id)
        .first()
    )
    if payment is None:
        raise ValidationError("Payment was not found")
    if payment.version != expected_version:
        raise ValidationError("Payment changed; refresh before retrying")
    target = resolve_stage(company, CommercialStage.EntityType.PAYMENT, target_code)
    assert_transition(payment.stage, target)
    before = payment.stage.code
    if target.outcome == CommercialStage.Outcome.POSTED:
        _assert_checker(company, payment.created_by_public_id, actor.user_public_id)
        _assert_period_open(payment.period)
        invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
        if payment.payment_type == Payment.PaymentType.STANDARD:
            if payment.amount > invoice.outstanding_amount:
                raise ValidationError("Payment exceeds the current outstanding amount")
            invoice.outstanding_amount = _money(invoice.outstanding_amount - payment.amount)
        else:
            if payment.amount > invoice.retention_amount:
                raise ValidationError("Retention release exceeds retained value")
            invoice.retention_amount = _money(invoice.retention_amount - payment.amount)
            invoice.outstanding_amount = _money(invoice.outstanding_amount + payment.amount)
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        sign = Decimal("-1") if invoice.invoice_type == Invoice.InvoiceType.VENDOR else Decimal("1")
        entry_type = (
            CommercialLedgerEntry.EntryType.RETENTION
            if payment.payment_type == Payment.PaymentType.RETENTION_RELEASE
            else CommercialLedgerEntry.EntryType.PAYMENT
        )
        _ledger(
            company=company,
            project=invoice.project,
            period=payment.period,
            entry_type=entry_type,
            amount=sign * payment.amount,
            currency=payment.currency,
            source_type="payment",
            source_public_id=payment.public_id,
            source_line_key="posted",
            actor=actor,
            description=payment.reference,
        )
        payment.posted_by_public_id = actor.user_public_id
        payment.posted_at = timezone.now()
    if target.outcome == CommercialStage.Outcome.REVERSED:
        if payment.posted_at is None or payment.reversed_at is not None:
            raise ValidationError("Only a posted, unreversed payment can be reversed")
        reversal_period = _period(company, period_public_id) if period_public_id else payment.period
        _assert_period_open(reversal_period)
        invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
        original = CommercialLedgerEntry.objects.filter(
            company=company,
            source_type="payment",
            source_public_id=payment.public_id,
            source_line_key="posted",
        ).first()
        if original is None:
            raise ValidationError("Payment posting fact was not found")
        _ledger(
            company=company,
            project=invoice.project,
            period=reversal_period,
            entry_type=CommercialLedgerEntry.EntryType.REVERSAL,
            amount=-original.amount,
            currency=payment.currency,
            source_type="payment_reversal",
            source_public_id=payment.public_id,
            source_line_key="reversed",
            actor=actor,
            description=f"Reversal of {payment.payment_number}",
            reversal_of=original,
        )
        if payment.payment_type == Payment.PaymentType.STANDARD:
            invoice.outstanding_amount = _money(invoice.outstanding_amount + payment.amount)
        else:
            invoice.retention_amount = _money(invoice.retention_amount + payment.amount)
            invoice.outstanding_amount = _money(
                max(Decimal("0"), invoice.outstanding_amount - payment.amount)
            )
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        payment.reversed_at = timezone.now()
    payment.stage = target
    payment.version += 1
    payment.full_clean()
    payment.save()
    _audit(
        actor,
        company,
        "finance.payment.transitioned",
        "payment",
        payment.public_id,
        before={"stage": before},
        after={"stage": target.code, "version": payment.version},
        reason_code=reason.strip(),
    )
    _event(
        actor,
        company,
        "finance.payment.transitioned",
        "payment",
        payment.public_id,
        payment.version,
        {"from": before, "to": target.code},
    )
    return payment


@transaction.atomic
def create_adjustment(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    period_public_id: uuid.UUID,
    posting_number: str,
    entry_type: str,
    cost_code: str,
    amount: Decimal,
    currency: str | None,
    description: str,
) -> CommercialAdjustment:
    project = _project(company, project_public_id)
    period = _period(company, period_public_id)
    _assert_period_open(period)
    adjustment = CommercialAdjustment(
        company=company,
        project=project,
        period=period,
        posting_number=posting_number.strip().upper(),
        entry_type=entry_type,
        cost_code=cost_code.strip().upper(),
        amount=_money(amount),
        currency=(currency or company.currency).upper(),
        description=description.strip(),
        created_by_public_id=actor.user_public_id,
        posted_at=timezone.now(),
    )
    adjustment.full_clean()
    adjustment.save()
    _ledger(
        company=company,
        project=project,
        period=period,
        entry_type=entry_type,
        amount=adjustment.amount,
        currency=adjustment.currency,
        source_type="commercial_adjustment",
        source_public_id=adjustment.public_id,
        source_line_key=adjustment.cost_code,
        actor=actor,
        description=adjustment.description,
    )
    _audit(
        actor,
        company,
        "finance.adjustment.posted",
        "commercial_adjustment",
        adjustment.public_id,
        after={
            "posting_number": adjustment.posting_number,
            "entry_type": adjustment.entry_type,
            "amount": str(adjustment.amount),
        },
    )
    _event(
        actor,
        company,
        "finance.adjustment.posted",
        "commercial_adjustment",
        adjustment.public_id,
        adjustment.version,
        {"project_public_id": str(project.public_id), "entry_type": adjustment.entry_type},
    )
    return adjustment


def finance_summary(company: Company) -> dict[str, Any]:
    budgets = ProjectBudget.objects.filter(company=company)
    variations = Variation.objects.filter(company=company)
    invoices = Invoice.objects.filter(company=company)
    payments = Payment.objects.filter(company=company, posted_at__isnull=False)
    ledger = CommercialLedgerEntry.objects.filter(company=company)
    adjustments = CommercialAdjustment.objects.filter(company=company)
    today = timezone.localdate()
    return {
        "budgets": budgets.count(),
        "approved_budget": str(budgets.aggregate(v=Sum("approved_total"))["v"] or Decimal("0")),
        "variations": variations.count(),
        "variation_value": str(variations.aggregate(v=Sum("total_amount"))["v"] or Decimal("0")),
        "invoices": invoices.count(),
        "invoice_value": str(invoices.aggregate(v=Sum("total_amount"))["v"] or Decimal("0")),
        "outstanding": str(invoices.aggregate(v=Sum("outstanding_amount"))["v"] or Decimal("0")),
        "overdue_invoices": invoices.filter(due_date__lt=today, outstanding_amount__gt=0).count(),
        "payments_posted": payments.count(),
        "ledger_entries": ledger.count(),
        "adjustments": adjustments.count(),
        "locked_periods": FinancialPeriod.objects.filter(
            company=company, locked_at__isnull=False
        ).count(),
        "currency": company.currency,
    }
