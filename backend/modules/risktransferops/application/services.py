from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.risktransferops.models import (
    GuaranteeInstrument,
    InstrumentCall,
    InsuranceClaim,
    InsuranceCoverage,
    InsuranceProgram,
    LossEvent,
    PremiumSchedule,
    RiskCounterparty,
    RiskTransferEvent,
    RiskTransferPolicyVersion,
)
from modules.tenant.models import Company


def _record(
    *,
    company: Company,
    action: str,
    event_type: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    version: int,
    after: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            before=before or {},
            after=after,
        )
    )
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload=after,
        )
    )


def seed_defaults(company: Company) -> dict[str, int]:
    _, created = RiskTransferPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "expiry_alert_days": 45,
            "claim_notification_sla_days": 7,
            "minimum_coverage_percent": Decimal("100.0000"),
            "configuration": {
                "phase": 45,
                "release": "insurance-bonds-guarantees-risk-transfer-operations",
                "insurance_provider": "PROVIDER_NEUTRAL",
                "surety_provider": "PROVIDER_NEUTRAL",
                "bank_guarantee_provider": "PROVIDER_NEUTRAL",
                "coverage_catalogue": "TENANT_CONFIGURABLE",
                "claim_workflow": "TENANT_CONFIGURABLE",
                "regional_insurance_rules": "TENANT_CONFIGURABLE",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in (
        "program_code",
        "counterparty_code",
        "policy_number",
        "installment_number",
        "loss_number",
        "claim_number",
        "instrument_number",
        "call_number",
    ):
        value = getattr(item, field, None)
        if value:
            return str(value)
    return str(item.public_id)


def _create(model, *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, event: str, **data: Any):
    item = model(company=company, **data)
    item.full_clean()
    item.save()
    _record(
        company=company,
        action="CREATE",
        event_type=event,
        entity_type=model.__name__,
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=getattr(item, "version", 1),
        after={"code": _identity(item), "status": getattr(item, "status_code", "RECORDED")},
    )
    return item


def _check_version(item: Any, expected_version: int, message: str) -> None:
    if item.version != expected_version:
        raise ValidationError(message)


def _maker_checker(item: Any, actor_public_id: uuid.UUID, field: str = "created_by_public_id") -> None:
    if getattr(item, field, None) == actor_public_id:
        raise ValidationError("The record creator cannot independently approve or verify the same record.")


def _transition(
    *,
    item: Any,
    model: Any,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str,
    allowed: dict[str, set[str]],
    event_type: str,
    approve_statuses: set[str] | None = None,
    close_statuses: set[str] | None = None,
) -> Any:
    item = model.objects.select_for_update().get(pk=item.pk)
    _check_version(item, expected_version, f"{model.__name__} changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    if status_code not in allowed.get(item.status_code, set()):
        raise ValidationError(f"Invalid {model.__name__} transition from {item.status_code} to {status_code}.")
    approve_statuses = approve_statuses or {"APPROVED", "VERIFIED"}
    close_statuses = close_statuses or {"CLOSED", "CANCELLED", "REJECTED"}
    if status_code in approve_statuses:
        _maker_checker(item, actor_public_id)
    before = {"status": item.status_code, "version": item.version}
    item.status_code = status_code
    if hasattr(item, "decision_note"):
        item.decision_note = note
    if hasattr(item, "verification_note"):
        item.verification_note = note
    if status_code in approve_statuses:
        if hasattr(item, "approved_by_public_id"):
            item.approved_by_public_id = actor_public_id
            item.approved_at = timezone.now()
        if hasattr(item, "verified_by_public_id"):
            item.verified_by_public_id = actor_public_id
            item.verified_at = timezone.now()
    elif status_code in {"DRAFT", "PENDING", "REJECTED"}:
        if hasattr(item, "approved_by_public_id"):
            item.approved_by_public_id = None
            item.approved_at = None
        if hasattr(item, "verified_by_public_id"):
            item.verified_by_public_id = None
            item.verified_at = None
    if status_code in close_statuses and hasattr(item, "closed_by_public_id"):
        item.closed_by_public_id = actor_public_id
        item.closed_at = timezone.now()
        item.closure_note = note
    item.version += 1
    item.full_clean()
    item.save()
    _record(
        company=item.company,
        action="TRANSITION",
        event_type=event_type,
        entity_type=model.__name__,
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=item.version,
        before=before,
        after={"status": item.status_code, "note": note},
    )
    return item


PROGRAM_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
    "REJECTED": {"DRAFT"},
    "APPROVED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"SUSPENDED", "CLOSED"},
    "SUSPENDED": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}
GENERIC_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
    "REJECTED": {"DRAFT"},
    "APPROVED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"SUSPENDED", "EXPIRED", "CLOSED", "CANCELLED"},
    "SUSPENDED": {"ACTIVE", "CLOSED", "CANCELLED"},
    "EXPIRED": {"CLOSED", "RENEWED"},
    "RENEWED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}


@transaction.atomic
def create_counterparty(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> RiskCounterparty:
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(RiskCounterparty, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.counterparty.created", **data)


@transaction.atomic
def transition_counterparty(*, counterparty: RiskCounterparty, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> RiskCounterparty:
    allowed = {"PENDING": {"VERIFIED", "REJECTED"}, "REJECTED": {"PENDING"}, "VERIFIED": {"SUSPENDED"}, "SUSPENDED": {"VERIFIED"}}
    return _transition(item=counterparty, model=RiskCounterparty, status_code=status_code, expected_version=expected_version, actor_public_id=actor_public_id, correlation_id=correlation_id, note=note, allowed=allowed, event_type="risktransfer.counterparty.transitioned", approve_statuses={"VERIFIED"})


@transaction.atomic
def create_program(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> InsuranceProgram:
    data.setdefault("owner_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    return _create(InsuranceProgram, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.program.created", **data)


@transaction.atomic
def transition_program(*, program: InsuranceProgram, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> InsuranceProgram:
    target_status = status_code.strip().upper()
    if target_status == "APPROVED" and program.aggregate_exposure <= 0:
        raise ValidationError("A positive aggregate exposure is required before program approval.")
    if target_status == "APPROVED" and program.owner_public_id == actor_public_id:
        raise ValidationError("The program owner cannot independently approve the same insurance program.")
    return _transition(item=program, model=InsuranceProgram, status_code=status_code, expected_version=expected_version, actor_public_id=actor_public_id, correlation_id=correlation_id, note=note, allowed=PROGRAM_TRANSITIONS, event_type="risktransfer.program.transitioned", approve_statuses={"APPROVED"})


@transaction.atomic
def create_coverage(*, company: Company, program: InsuranceProgram, counterparty: RiskCounterparty, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> InsuranceCoverage:
    if program.company_id != company.id or counterparty.company_id != company.id:
        raise ValidationError("Insurance coverage cannot cross companies.")
    if counterparty.status_code != "VERIFIED":
        raise ValidationError("Insurer or risk counterparty must be verified before coverage is recorded.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(InsuranceCoverage, company=company, program=program, counterparty=counterparty, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.coverage.created", **data)


@transaction.atomic
def transition_coverage(*, coverage: InsuranceCoverage, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> InsuranceCoverage:
    return _transition(item=coverage, model=InsuranceCoverage, status_code=status_code, expected_version=expected_version, actor_public_id=actor_public_id, correlation_id=correlation_id, note=note, allowed=GENERIC_TRANSITIONS, event_type="risktransfer.coverage.transitioned", approve_statuses={"APPROVED"})


@transaction.atomic
def create_premium(*, company: Company, coverage: InsuranceCoverage, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> PremiumSchedule:
    if coverage.company_id != company.id:
        raise ValidationError("Premium schedule cannot cross companies.")
    data.setdefault("currency_code", coverage.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(PremiumSchedule, company=company, coverage=coverage, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.premium.created", **data)


@transaction.atomic
def transition_premium(*, premium: PremiumSchedule, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "", paid_amount: Decimal | None = None, paid_on: date | None = None, payment_reference: str = "") -> PremiumSchedule:
    premium = PremiumSchedule.objects.select_for_update().get(pk=premium.pk)
    _check_version(premium, expected_version, "Premium schedule changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {"DUE": {"PAID", "PARTIALLY_PAID", "WAIVED", "CANCELLED"}, "PARTIALLY_PAID": {"PAID", "WAIVED", "CANCELLED"}, "PAID": set(), "WAIVED": set(), "CANCELLED": set()}
    if status_code not in allowed.get(premium.status_code, set()):
        raise ValidationError(f"Invalid premium transition from {premium.status_code} to {status_code}.")
    before = {"status": premium.status_code, "paid_amount": str(premium.paid_amount), "version": premium.version}
    if paid_amount is not None:
        premium.paid_amount = paid_amount
    if status_code == "PAID":
        premium.paid_amount = premium.amount
        premium.paid_on = paid_on or timezone.localdate()
        premium.payment_reference = payment_reference
    elif status_code == "PARTIALLY_PAID":
        if premium.paid_amount <= 0 or premium.paid_amount >= premium.amount:
            raise ValidationError("A partial premium payment must be greater than zero and below the installment amount.")
        premium.paid_on = paid_on or timezone.localdate()
        premium.payment_reference = payment_reference
    premium.status_code = status_code
    premium.version += 1
    premium.full_clean()
    premium.save()
    _record(company=premium.company, action="TRANSITION", event_type="risktransfer.premium.transitioned", entity_type="PremiumSchedule", entity_public_id=premium.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=premium.version, before=before, after={"status": premium.status_code, "paid_amount": str(premium.paid_amount), "note": note})
    return premium


@transaction.atomic
def create_loss(*, company: Company, program: InsuranceProgram, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> LossEvent:
    if program.company_id != company.id:
        raise ValidationError("Loss event cannot cross companies.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("reporter_public_id", actor_public_id)
    return _create(LossEvent, company=company, program=program, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.loss.created", **data)


@transaction.atomic
def transition_loss(*, loss: LossEvent, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> LossEvent:
    allowed = {"OPEN": {"INVESTIGATING", "CLOSED"}, "INVESTIGATING": {"CLAIMED", "CLOSED"}, "CLAIMED": {"RECOVERING", "CLOSED"}, "RECOVERING": {"CLOSED"}, "CLOSED": set()}
    return _transition(item=loss, model=LossEvent, status_code=status_code, expected_version=expected_version, actor_public_id=actor_public_id, correlation_id=correlation_id, note=note, allowed=allowed, event_type="risktransfer.loss.transitioned", approve_statuses=set(), close_statuses={"CLOSED"})


@transaction.atomic
def create_claim(*, company: Company, loss_event: LossEvent, coverage: InsuranceCoverage, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> InsuranceClaim:
    if loss_event.company_id != company.id or coverage.company_id != company.id:
        raise ValidationError("Insurance claim cannot cross companies.")
    if loss_event.program_id != coverage.program_id:
        raise ValidationError("Loss event and coverage must belong to the same program.")
    if coverage.status_code not in {"APPROVED", "ACTIVE", "EXPIRED", "RENEWED"}:
        raise ValidationError("Coverage must be approved or active before a claim is recorded.")
    data.setdefault("currency_code", coverage.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(InsuranceClaim, company=company, loss_event=loss_event, coverage=coverage, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.claim.created", **data)


@transaction.atomic
def transition_claim(*, claim: InsuranceClaim, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "", recovered_amount: Decimal | None = None, settlement_reference: str = "", settled_on: date | None = None) -> InsuranceClaim:
    claim = InsuranceClaim.objects.select_for_update().get(pk=claim.pk)
    _check_version(claim, expected_version, "Insurance claim changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {"DRAFT": {"NOTIFIED", "CANCELLED"}, "NOTIFIED": {"ADMITTED", "REJECTED", "UNDER_REVIEW"}, "UNDER_REVIEW": {"ADMITTED", "REJECTED"}, "ADMITTED": {"SETTLED", "PARTIALLY_SETTLED"}, "PARTIALLY_SETTLED": {"SETTLED", "CLOSED"}, "SETTLED": {"CLOSED"}, "REJECTED": {"CLOSED"}, "CANCELLED": set(), "CLOSED": set()}
    if status_code not in allowed.get(claim.status_code, set()):
        raise ValidationError(f"Invalid claim transition from {claim.status_code} to {status_code}.")
    if status_code == "ADMITTED":
        _maker_checker(claim, actor_public_id)
    before = {"status": claim.status_code, "recovered_amount": str(claim.recovered_amount), "version": claim.version}
    if recovered_amount is not None:
        claim.recovered_amount = recovered_amount
    if status_code == "ADMITTED":
        claim.approved_by_public_id = actor_public_id
        claim.approved_at = timezone.now()
    if status_code in {"SETTLED", "PARTIALLY_SETTLED"}:
        if claim.recovered_amount <= 0:
            raise ValidationError("A positive recovered amount is required before settlement.")
        claim.settlement_reference = settlement_reference
        claim.settled_on = settled_on or timezone.localdate()
    claim.status_code = status_code
    claim.decision_note = note
    claim.version += 1
    claim.full_clean()
    claim.save()
    _record(company=claim.company, action="TRANSITION", event_type="risktransfer.claim.transitioned", entity_type="InsuranceClaim", entity_public_id=claim.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=claim.version, before=before, after={"status": claim.status_code, "recovered_amount": str(claim.recovered_amount), "note": note})
    return claim


@transaction.atomic
def create_instrument(*, company: Company, program: InsuranceProgram, counterparty: RiskCounterparty, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> GuaranteeInstrument:
    if program.company_id != company.id or counterparty.company_id != company.id:
        raise ValidationError("Guarantee instrument cannot cross companies.")
    if counterparty.status_code != "VERIFIED":
        raise ValidationError("Bank, insurer or surety must be verified before an instrument is recorded.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(GuaranteeInstrument, company=company, program=program, counterparty=counterparty, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.instrument.created", **data)


@transaction.atomic
def transition_instrument(*, instrument: GuaranteeInstrument, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> GuaranteeInstrument:
    return _transition(item=instrument, model=GuaranteeInstrument, status_code=status_code, expected_version=expected_version, actor_public_id=actor_public_id, correlation_id=correlation_id, note=note, allowed=GENERIC_TRANSITIONS, event_type="risktransfer.instrument.transitioned", approve_statuses={"APPROVED"})


@transaction.atomic
def create_call(*, company: Company, instrument: GuaranteeInstrument, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> InstrumentCall:
    if instrument.company_id != company.id:
        raise ValidationError("Guarantee call cannot cross companies.")
    if instrument.status_code not in {"APPROVED", "ACTIVE", "SUSPENDED"}:
        raise ValidationError("Guarantee instrument must be approved or active before it can be called.")
    proposed = Decimal(str(data.get("amount", 0)))
    existing = InstrumentCall.objects.filter(company=company, instrument=instrument).exclude(status_code__in=["REJECTED", "CANCELLED"]).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if existing + proposed > instrument.amount:
        raise ValidationError("Aggregate guarantee calls cannot exceed the instrument amount.")
    data.setdefault("currency_code", instrument.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(InstrumentCall, company=company, instrument=instrument, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.call.created", **data)


@transaction.atomic
def transition_call(*, call: InstrumentCall, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "", settlement_reference: str = "", settled_on: date | None = None) -> InstrumentCall:
    call = InstrumentCall.objects.select_for_update().get(pk=call.pk)
    _check_version(call, expected_version, "Guarantee call changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {"DRAFT": {"SUBMITTED", "CANCELLED"}, "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"}, "REJECTED": {"DRAFT"}, "APPROVED": {"SETTLED", "DISPUTED"}, "DISPUTED": {"SETTLED", "CLOSED"}, "SETTLED": {"CLOSED"}, "CANCELLED": set(), "CLOSED": set()}
    if status_code not in allowed.get(call.status_code, set()):
        raise ValidationError(f"Invalid guarantee-call transition from {call.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(call, actor_public_id)
    before = {"status": call.status_code, "version": call.version}
    if status_code == "APPROVED":
        call.approved_by_public_id = actor_public_id
        call.approved_at = timezone.now()
    if status_code == "SETTLED":
        call.settlement_reference = settlement_reference
        call.settled_on = settled_on or timezone.localdate()
    call.status_code = status_code
    call.decision_note = note
    call.version += 1
    call.full_clean()
    call.save()
    _record(company=call.company, action="TRANSITION", event_type="risktransfer.call.transitioned", entity_type="InstrumentCall", entity_public_id=call.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=call.version, before=before, after={"status": call.status_code, "note": note})
    return call


@transaction.atomic
def create_event(*, company: Company, program: InsuranceProgram | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> RiskTransferEvent:
    if program and program.company_id != company.id:
        raise ValidationError("Risk-transfer event cannot cross companies.")
    data.setdefault("event_on", timezone.now())
    data.setdefault("actor_public_id", actor_public_id)
    return _create(RiskTransferEvent, company=company, program=program, actor_public_id=actor_public_id, correlation_id=correlation_id, event="risktransfer.event.created", **data)
