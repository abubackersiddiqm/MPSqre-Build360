from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.capitalops.models import (
    CapitalCommitment,
    CapitalEvent,
    CapitalPolicyVersion,
    CovenantTest,
    DebtFacility,
    DrawdownRequest,
    FundingProgram,
    InvestorDistribution,
    InvestorProfile,
    JointVentureArrangement,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
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
    _, created = CapitalPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "covenant_alert_days": 30,
            "commitment_expiry_alert_days": 45,
            "maximum_leverage_percent": Decimal("70.0000"),
            "configuration": {
                "phase": 44,
                "release": "capital-joint-venture-funding-investor-operations",
                "banking_provider": "PROVIDER_NEUTRAL",
                "payment_rail": "PROVIDER_NEUTRAL",
                "investor_registry": "TENANT_CONFIGURABLE",
                "funding_workflow": "TENANT_CONFIGURABLE",
                "regional_securities_rules": "TENANT_CONFIGURABLE",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in (
        "program_code",
        "investor_code",
        "venture_code",
        "commitment_number",
        "facility_code",
        "request_number",
        "test_number",
        "distribution_number",
    ):
        value = getattr(item, field, None)
        if value:
            return str(value)
    return str(item.public_id)


def _create(
    model,
    *,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    event: str,
    **data: Any,
):
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
        after={
            "code": _identity(item),
            "status": getattr(item, "status_code", getattr(item, "kyc_status_code", "RECORDED")),
        },
    )
    return item


def _check_version(item: Any, expected_version: int, message: str) -> None:
    if item.version != expected_version:
        raise ValidationError(message)


def _maker_checker(item: Any, actor_public_id: uuid.UUID, field: str = "created_by_public_id") -> None:
    if getattr(item, field, None) == actor_public_id:
        raise ValidationError("The record creator cannot independently approve or verify the same record.")


@transaction.atomic
def create_program(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> FundingProgram:
    data.setdefault("sponsor_public_id", actor_public_id)
    data.setdefault("currency_code", company.currency)
    return _create(
        FundingProgram,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.program.created",
        **data,
    )


@transaction.atomic
def transition_program(
    *,
    program: FundingProgram,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> FundingProgram:
    program = FundingProgram.objects.select_for_update().get(pk=program.pk)
    _check_version(program, expected_version, "Funding program changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"SUSPENDED", "CLOSED"},
        "SUSPENDED": {"ACTIVE", "CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(program.status_code, set()):
        raise ValidationError(f"Invalid funding-program transition from {program.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(program, actor_public_id, "sponsor_public_id")
        if program.target_capital <= 0:
            raise ValidationError("A positive capital target is required before program approval.")
        if program.target_equity + program.target_debt > program.target_capital:
            raise ValidationError("Equity and debt targets exceed the approved total capital target.")
    before = {"status": program.status_code, "version": program.version}
    program.status_code = status_code
    program.decision_note = note
    if status_code == "APPROVED":
        program.approved_by_public_id = actor_public_id
        program.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        program.approved_by_public_id = None
        program.approved_at = None
    program.version += 1
    program.full_clean()
    program.save()
    _record(
        company=program.company,
        action="TRANSITION",
        event_type="capital.program.transitioned",
        entity_type="FundingProgram",
        entity_public_id=program.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=program.version,
        before=before,
        after={"status": program.status_code, "note": note},
    )
    return program


@transaction.atomic
def create_investor(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> InvestorProfile:
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(
        InvestorProfile,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.investor.created",
        **data,
    )


@transaction.atomic
def transition_investor(
    *,
    investor: InvestorProfile,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> InvestorProfile:
    investor = InvestorProfile.objects.select_for_update().get(pk=investor.pk)
    _check_version(investor, expected_version, "Investor record changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {"PENDING": {"VERIFIED", "REJECTED"}, "REJECTED": {"PENDING"}, "VERIFIED": {"SUSPENDED"}, "SUSPENDED": {"VERIFIED"}}
    if status_code not in allowed.get(investor.kyc_status_code, set()):
        raise ValidationError(f"Invalid investor verification transition from {investor.kyc_status_code} to {status_code}.")
    if status_code == "VERIFIED":
        _maker_checker(investor, actor_public_id)
    before = {"status": investor.kyc_status_code, "version": investor.version}
    investor.kyc_status_code = status_code
    investor.verification_note = note
    if status_code == "VERIFIED":
        investor.verified_by_public_id = actor_public_id
        investor.verified_at = timezone.now()
    elif status_code in {"PENDING", "REJECTED"}:
        investor.verified_by_public_id = None
        investor.verified_at = None
    investor.version += 1
    investor.full_clean()
    investor.save()
    _record(
        company=investor.company,
        action="TRANSITION",
        event_type="capital.investor.transitioned",
        entity_type="InvestorProfile",
        entity_public_id=investor.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=investor.version,
        before=before,
        after={"status": investor.kyc_status_code, "note": note},
    )
    return investor


@transaction.atomic
def create_joint_venture(
    *, company: Company, program: FundingProgram, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> JointVentureArrangement:
    if program.company_id != company.id:
        raise ValidationError("Joint venture cannot cross companies.")
    proposed = Decimal(str(data.get("ownership_percent", 0)))
    current = JointVentureArrangement.objects.filter(company=company, program=program).exclude(status_code__in=["CLOSED", "CANCELLED", "REJECTED"]).aggregate(total=Sum("ownership_percent"))["total"] or Decimal("0")
    if current + proposed > Decimal("100"):
        raise ValidationError("Active joint-venture ownership percentages cannot exceed 100 percent.")
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(
        JointVentureArrangement,
        company=company,
        program=program,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.joint_venture.created",
        **data,
    )


@transaction.atomic
def transition_joint_venture(
    *,
    joint_venture: JointVentureArrangement,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> JointVentureArrangement:
    joint_venture = JointVentureArrangement.objects.select_for_update().get(pk=joint_venture.pk)
    _check_version(joint_venture, expected_version, "Joint venture changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(joint_venture.status_code, set()):
        raise ValidationError(f"Invalid joint-venture transition from {joint_venture.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(joint_venture, actor_public_id)
    before = {"status": joint_venture.status_code, "version": joint_venture.version}
    joint_venture.status_code = status_code
    joint_venture.decision_note = note
    if status_code == "APPROVED":
        joint_venture.approved_by_public_id = actor_public_id
        joint_venture.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        joint_venture.approved_by_public_id = None
        joint_venture.approved_at = None
    joint_venture.version += 1
    joint_venture.full_clean()
    joint_venture.save()
    _record(
        company=joint_venture.company,
        action="TRANSITION",
        event_type="capital.joint_venture.transitioned",
        entity_type="JointVentureArrangement",
        entity_public_id=joint_venture.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=joint_venture.version,
        before=before,
        after={"status": joint_venture.status_code, "note": note},
    )
    return joint_venture


@transaction.atomic
def create_commitment(
    *,
    company: Company,
    program: FundingProgram,
    investor: InvestorProfile | None,
    joint_venture: JointVentureArrangement | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> CapitalCommitment:
    if program.company_id != company.id:
        raise ValidationError("Commitment cannot cross companies.")
    if bool(investor) == bool(joint_venture):
        raise ValidationError("Select exactly one investor or joint-venture counterparty.")
    if investor and investor.kyc_status_code != "VERIFIED":
        raise ValidationError("Investor must be verified before a commitment is recorded.")
    if joint_venture and joint_venture.status_code not in {"APPROVED", "ACTIVE"}:
        raise ValidationError("Joint venture must be approved before a commitment is recorded.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(
        CapitalCommitment,
        company=company,
        program=program,
        investor=investor,
        joint_venture=joint_venture,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.commitment.created",
        **data,
    )


@transaction.atomic
def transition_commitment(
    *,
    commitment: CapitalCommitment,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> CapitalCommitment:
    commitment = CapitalCommitment.objects.select_for_update().get(pk=commitment.pk)
    _check_version(commitment, expected_version, "Capital commitment changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"FULLY_FUNDED", "CANCELLED"},
        "FULLY_FUNDED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(commitment.status_code, set()):
        raise ValidationError(f"Invalid commitment transition from {commitment.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(commitment, actor_public_id)
    if status_code == "FULLY_FUNDED" and commitment.funded_amount < commitment.committed_amount:
        raise ValidationError("Commitment cannot be marked fully funded until the committed amount is received.")
    before = {"status": commitment.status_code, "version": commitment.version}
    commitment.status_code = status_code
    commitment.decision_note = note
    if status_code == "APPROVED":
        commitment.approved_by_public_id = actor_public_id
        commitment.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        commitment.approved_by_public_id = None
        commitment.approved_at = None
    commitment.version += 1
    commitment.full_clean()
    commitment.save()
    _record(
        company=commitment.company,
        action="TRANSITION",
        event_type="capital.commitment.transitioned",
        entity_type="CapitalCommitment",
        entity_public_id=commitment.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=commitment.version,
        before=before,
        after={"status": commitment.status_code, "note": note},
    )
    return commitment


@transaction.atomic
def create_debt_facility(
    *, company: Company, program: FundingProgram, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> DebtFacility:
    if program.company_id != company.id:
        raise ValidationError("Debt facility cannot cross companies.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(
        DebtFacility,
        company=company,
        program=program,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.debt_facility.created",
        **data,
    )


@transaction.atomic
def transition_debt_facility(
    *,
    facility: DebtFacility,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> DebtFacility:
    facility = DebtFacility.objects.select_for_update().get(pk=facility.pk)
    _check_version(facility, expected_version, "Debt facility changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"MATURED", "CLOSED", "SUSPENDED"},
        "SUSPENDED": {"ACTIVE", "CLOSED"},
        "MATURED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(facility.status_code, set()):
        raise ValidationError(f"Invalid debt-facility transition from {facility.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(facility, actor_public_id)
    before = {"status": facility.status_code, "version": facility.version}
    facility.status_code = status_code
    facility.decision_note = note
    if status_code == "APPROVED":
        facility.approved_by_public_id = actor_public_id
        facility.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        facility.approved_by_public_id = None
        facility.approved_at = None
    facility.version += 1
    facility.full_clean()
    facility.save()
    _record(
        company=facility.company,
        action="TRANSITION",
        event_type="capital.debt_facility.transitioned",
        entity_type="DebtFacility",
        entity_public_id=facility.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=facility.version,
        before=before,
        after={"status": facility.status_code, "note": note},
    )
    return facility


def _drawdown_reserved(source_filter: dict[str, Any]) -> Decimal:
    return DrawdownRequest.objects.filter(
        **source_filter,
        status_code__in=["APPROVED", "DISBURSED", "SETTLED"],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")


@transaction.atomic
def create_drawdown(
    *,
    company: Company,
    program: FundingProgram,
    debt_facility: DebtFacility | None,
    commitment: CapitalCommitment | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> DrawdownRequest:
    if bool(debt_facility) == bool(commitment):
        raise ValidationError("Select exactly one debt facility or capital commitment source.")
    amount = Decimal(str(data.get("amount", 0)))
    if debt_facility:
        if debt_facility.status_code not in {"APPROVED", "ACTIVE"}:
            raise ValidationError("Debt facility must be approved or active before drawdown.")
        available = debt_facility.principal_limit - _drawdown_reserved({"company": company, "debt_facility": debt_facility})
        if amount > available:
            raise ValidationError("Drawdown exceeds the remaining debt-facility limit.")
        data.setdefault("request_type_code", "DEBT_DRAWDOWN")
        data.setdefault("currency_code", debt_facility.currency_code)
    if commitment:
        if commitment.status_code not in {"APPROVED", "ACTIVE"}:
            raise ValidationError("Commitment must be approved or active before a capital call.")
        available = commitment.committed_amount - _drawdown_reserved({"company": company, "commitment": commitment})
        if amount > available:
            raise ValidationError("Capital call exceeds the remaining commitment amount.")
        data.setdefault("request_type_code", "EQUITY_CALL")
        data.setdefault("currency_code", commitment.currency_code)
    data.setdefault("requested_by_public_id", actor_public_id)
    return _create(
        DrawdownRequest,
        company=company,
        program=program,
        debt_facility=debt_facility,
        commitment=commitment,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.drawdown.created",
        **data,
    )


@transaction.atomic
def transition_drawdown(
    *,
    drawdown: DrawdownRequest,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
    disbursement_reference: str = "",
    disbursed_on=None,
) -> DrawdownRequest:
    drawdown = DrawdownRequest.objects.select_for_update(of=("self",)).select_related("commitment", "debt_facility").get(pk=drawdown.pk)
    _check_version(drawdown, expected_version, "Drawdown request changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"DISBURSED", "CANCELLED"},
        "DISBURSED": {"SETTLED"},
        "SETTLED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(drawdown.status_code, set()):
        raise ValidationError(f"Invalid drawdown transition from {drawdown.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(drawdown, actor_public_id, "requested_by_public_id")
    if status_code == "DISBURSED" and not (disbursement_reference or drawdown.disbursement_reference):
        raise ValidationError("Disbursement reference is required before marking a drawdown disbursed.")
    before = {"status": drawdown.status_code, "version": drawdown.version}
    drawdown.status_code = status_code
    drawdown.decision_note = note
    if status_code == "APPROVED":
        drawdown.approved_by_public_id = actor_public_id
        drawdown.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        drawdown.approved_by_public_id = None
        drawdown.approved_at = None
    if status_code == "DISBURSED":
        drawdown.disbursement_reference = disbursement_reference or drawdown.disbursement_reference
        drawdown.disbursed_on = disbursed_on or timezone.localdate()
        if drawdown.commitment_id:
            commitment = CapitalCommitment.objects.select_for_update().get(pk=drawdown.commitment_id)
            commitment.called_amount = min(commitment.committed_amount, commitment.called_amount + drawdown.amount)
            commitment.funded_amount = min(commitment.committed_amount, commitment.funded_amount + drawdown.amount)
            if commitment.funded_amount >= commitment.committed_amount and commitment.status_code in {"APPROVED", "ACTIVE"}:
                commitment.status_code = "FULLY_FUNDED"
            commitment.version += 1
            commitment.full_clean()
            commitment.save()
    drawdown.version += 1
    drawdown.full_clean()
    drawdown.save()
    _record(
        company=drawdown.company,
        action="TRANSITION",
        event_type="capital.drawdown.transitioned",
        entity_type="DrawdownRequest",
        entity_public_id=drawdown.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=drawdown.version,
        before=before,
        after={"status": drawdown.status_code, "note": note, "disbursement_reference": drawdown.disbursement_reference},
    )
    return drawdown


def _evaluate(operator: str, metric: Decimal, threshold: Decimal) -> bool:
    operator = operator.strip().upper()
    return {
        "LT": metric < threshold,
        "LTE": metric <= threshold,
        "GT": metric > threshold,
        "GTE": metric >= threshold,
        "EQ": metric == threshold,
    }.get(operator, False)


@transaction.atomic
def create_covenant_test(
    *, company: Company, facility: DebtFacility, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> CovenantTest:
    if facility.company_id != company.id:
        raise ValidationError("Covenant test cannot cross companies.")
    metric = Decimal(str(data.get("metric_value", 0)))
    threshold = Decimal(str(data.get("threshold_value", 0)))
    operator = str(data.get("threshold_operator", "LTE"))
    data["compliant"] = _evaluate(operator, metric, threshold)
    data.setdefault("tested_by_public_id", actor_public_id)
    return _create(
        CovenantTest,
        company=company,
        debt_facility=facility,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.covenant_test.created",
        **data,
    )


@transaction.atomic
def transition_covenant_test(
    *,
    test: CovenantTest,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
) -> CovenantTest:
    test = CovenantTest.objects.select_for_update().get(pk=test.pk)
    _check_version(test, expected_version, "Covenant test changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {"OPEN": {"REVIEWED"}, "REVIEWED": {"CLOSED", "WAIVED", "OPEN"}, "WAIVED": {"CLOSED"}, "CLOSED": set()}
    if status_code not in allowed.get(test.status_code, set()):
        raise ValidationError(f"Invalid covenant transition from {test.status_code} to {status_code}.")
    if status_code in {"REVIEWED", "WAIVED", "CLOSED"}:
        _maker_checker(test, actor_public_id, "tested_by_public_id")
    if status_code == "CLOSED" and not test.compliant and test.status_code != "WAIVED":
        raise ValidationError("A non-compliant covenant must be waived or remediated before closure.")
    before = {"status": test.status_code, "version": test.version}
    test.status_code = status_code
    test.decision_note = note
    if status_code in {"REVIEWED", "WAIVED", "CLOSED"}:
        test.reviewed_by_public_id = actor_public_id
        test.reviewed_at = timezone.now()
    test.version += 1
    test.full_clean()
    test.save()
    _record(
        company=test.company,
        action="TRANSITION",
        event_type="capital.covenant_test.transitioned",
        entity_type="CovenantTest",
        entity_public_id=test.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=test.version,
        before=before,
        after={"status": test.status_code, "compliant": test.compliant, "note": note},
    )
    return test


@transaction.atomic
def create_distribution(
    *,
    company: Company,
    program: FundingProgram,
    investor: InvestorProfile | None,
    joint_venture: JointVentureArrangement | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    **data: Any,
) -> InvestorDistribution:
    if bool(investor) == bool(joint_venture):
        raise ValidationError("Select exactly one investor or joint-venture beneficiary.")
    data.setdefault("currency_code", program.currency_code)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(
        InvestorDistribution,
        company=company,
        program=program,
        investor=investor,
        joint_venture=joint_venture,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.distribution.created",
        **data,
    )


@transaction.atomic
def transition_distribution(
    *,
    distribution: InvestorDistribution,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
    note: str = "",
    payment_reference: str = "",
    paid_on=None,
) -> InvestorDistribution:
    distribution = InvestorDistribution.objects.select_for_update().get(pk=distribution.pk)
    _check_version(distribution, expected_version, "Distribution changed. Refresh and retry.")
    status_code = status_code.strip().upper()
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"PAID", "CANCELLED"},
        "PAID": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(distribution.status_code, set()):
        raise ValidationError(f"Invalid distribution transition from {distribution.status_code} to {status_code}.")
    if status_code == "APPROVED":
        _maker_checker(distribution, actor_public_id)
    if status_code == "PAID" and not (payment_reference or distribution.payment_reference):
        raise ValidationError("Payment reference is required before marking a distribution paid.")
    before = {"status": distribution.status_code, "version": distribution.version}
    distribution.status_code = status_code
    distribution.decision_note = note
    if status_code == "APPROVED":
        distribution.approved_by_public_id = actor_public_id
        distribution.approved_at = timezone.now()
    elif status_code in {"DRAFT", "REJECTED"}:
        distribution.approved_by_public_id = None
        distribution.approved_at = None
    if status_code == "PAID":
        distribution.payment_reference = payment_reference or distribution.payment_reference
        distribution.paid_on = paid_on or timezone.localdate()
    distribution.version += 1
    distribution.full_clean()
    distribution.save()
    _record(
        company=distribution.company,
        action="TRANSITION",
        event_type="capital.distribution.transitioned",
        entity_type="InvestorDistribution",
        entity_public_id=distribution.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=distribution.version,
        before=before,
        after={"status": distribution.status_code, "note": note, "payment_reference": distribution.payment_reference},
    )
    return distribution


@transaction.atomic
def create_event(
    *, company: Company, program: FundingProgram, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> CapitalEvent:
    data.setdefault("event_on", timezone.now())
    data.setdefault("actor_public_id", actor_public_id)
    return _create(
        CapitalEvent,
        company=company,
        program=program,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="capital.event.recorded",
        **data,
    )
