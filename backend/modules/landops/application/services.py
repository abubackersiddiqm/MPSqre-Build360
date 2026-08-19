from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.landops.models import (
    AcquisitionEvent,
    AcquisitionOpportunity,
    CommercialOffer,
    DueDiligenceCase,
    FeasibilityScenario,
    LandParcel,
    LandPolicyVersion,
    LandRisk,
    OwnershipInterest,
    StatutoryApproval,
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
    _, created = LandPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "due_diligence_target_days": 45,
            "approval_alert_days": 60,
            "minimum_margin_percent": Decimal("15.0000"),
            "configuration": {
                "phase": 43,
                "release": "land-acquisition-feasibility-statutory-approvals",
                "title_registry": "PROVIDER_NEUTRAL",
                "gis_provider": "PROVIDER_NEUTRAL",
                "valuation_methodology": "TENANT_CONFIGURABLE",
                "approval_catalogue": "TENANT_CONFIGURABLE",
                "regional_land_law": "TENANT_CONFIGURABLE",
            },
        },
    )
    return {"policy": int(created)}


def _identity(item: Any) -> str:
    for field in (
        "parcel_code",
        "case_number",
        "scenario_code",
        "opportunity_code",
        "offer_number",
        "approval_code",
        "risk_number",
        "owner_name",
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
        after={"code": _identity(item), "status": getattr(item, "status_code", getattr(item, "verification_status_code", "RECORDED"))},
    )
    return item


@transaction.atomic
def create_parcel(*, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> LandParcel:
    data.setdefault("owner_public_id", actor_public_id)
    return _create(LandParcel, company=company, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.parcel.created", **data)


@transaction.atomic
def create_ownership(*, company: Company, parcel: LandParcel, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> OwnershipInterest:
    if parcel.company_id != company.id:
        raise ValidationError("Ownership interest cannot cross companies.")
    data.setdefault("created_by_public_id", actor_public_id)
    existing_share = OwnershipInterest.objects.filter(company=company, parcel=parcel).aggregate(total=Sum("share_percent"))["total"] or Decimal("0")
    proposed = Decimal(str(data.get("share_percent", "100")))
    if existing_share + proposed > Decimal("100"):
        raise ValidationError("Ownership shares for a parcel cannot exceed 100 percent.")
    return _create(OwnershipInterest, company=company, parcel=parcel, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.ownership.created", **data)


@transaction.atomic
def verify_ownership(*, ownership: OwnershipInterest, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> OwnershipInterest:
    ownership = OwnershipInterest.objects.select_for_update().get(pk=ownership.pk)
    status_code = status_code.strip().upper()
    if ownership.version != expected_version:
        raise ValidationError("Ownership record changed. Refresh and retry.")
    if ownership.created_by_public_id == actor_public_id and status_code == "VERIFIED":
        raise ValidationError("The ownership record creator cannot independently verify the same record.")
    allowed = {"PENDING": {"VERIFIED", "REJECTED"}, "REJECTED": {"PENDING"}, "VERIFIED": {"PENDING"}}
    if status_code not in allowed.get(ownership.verification_status_code, set()):
        raise ValidationError(f"Invalid ownership transition from {ownership.verification_status_code} to {status_code}.")
    before = {"status": ownership.verification_status_code, "version": ownership.version}
    ownership.verification_status_code = status_code
    ownership.verified_by_public_id = actor_public_id if status_code == "VERIFIED" else None
    ownership.verified_at = timezone.now() if status_code == "VERIFIED" else None
    if note:
        ownership.encumbrance_summary = f"{ownership.encumbrance_summary}\n{note}".strip()
    ownership.version += 1
    ownership.full_clean()
    ownership.save()
    _record(company=ownership.company, action="TRANSITION", event_type="land.ownership.transitioned", entity_type="OwnershipInterest", entity_public_id=ownership.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=ownership.version, before=before, after={"status": ownership.verification_status_code, "note": note})
    return ownership


@transaction.atomic
def create_diligence(*, company: Company, parcel: LandParcel, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> DueDiligenceCase:
    if parcel.company_id != company.id:
        raise ValidationError("Due-diligence case cannot cross companies.")
    policy = LandPolicyVersion.objects.filter(company=company).order_by("-version").first()
    opened_on = data.get("opened_on") or timezone.localdate()
    data["opened_on"] = opened_on
    if data.get("target_on") is None:
        data["target_on"] = opened_on + timedelta(days=policy.due_diligence_target_days if policy else 45)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(DueDiligenceCase, company=company, parcel=parcel, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.diligence.created", **data)


@transaction.atomic
def transition_diligence(*, case: DueDiligenceCase, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> DueDiligenceCase:
    case = DueDiligenceCase.objects.select_for_update().get(pk=case.pk)
    status_code = status_code.strip().upper()
    if case.version != expected_version:
        raise ValidationError("Due-diligence case changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"IN_REVIEW", "CANCELLED"},
        "IN_REVIEW": {"CLEARED", "CONDITIONAL", "REJECTED", "DRAFT"},
        "CONDITIONAL": {"IN_REVIEW", "CLEARED", "REJECTED"},
        "REJECTED": {"DRAFT"},
        "CLEARED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(case.status_code, set()):
        raise ValidationError(f"Invalid due-diligence transition from {case.status_code} to {status_code}.")
    if status_code in {"CLEARED", "CONDITIONAL", "REJECTED"} and case.created_by_public_id == actor_public_id:
        raise ValidationError("The due-diligence creator cannot make the independent review decision.")
    if status_code == "CLEARED" and case.blockers:
        raise ValidationError("Clear the due-diligence blocker list before marking the case cleared.")
    before = {"status": case.status_code, "version": case.version}
    case.status_code = status_code
    case.decision_note = note
    if status_code in {"CLEARED", "CONDITIONAL", "REJECTED"}:
        case.reviewed_by_public_id = actor_public_id
        case.reviewed_at = timezone.now()
    else:
        case.reviewed_by_public_id = None
        case.reviewed_at = None
    case.version += 1
    case.full_clean()
    case.save()
    _record(company=case.company, action="TRANSITION", event_type="land.diligence.transitioned", entity_type="DueDiligenceCase", entity_public_id=case.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=case.version, before=before, after={"status": case.status_code, "note": note})
    return case


def _calculate_margin(data: dict[str, Any]) -> Decimal:
    revenue = Decimal(str(data.get("estimated_revenue", 0)))
    costs = sum(
        (Decimal(str(data.get(field, 0))) for field in ("land_cost", "construction_cost", "soft_cost", "finance_cost", "contingency_cost")),
        Decimal("0"),
    )
    if revenue <= 0:
        return Decimal("0")
    return ((revenue - costs) / revenue * Decimal("100")).quantize(Decimal("0.0001"))


@transaction.atomic
def create_feasibility(*, company: Company, parcel: LandParcel, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> FeasibilityScenario:
    if parcel.company_id != company.id:
        raise ValidationError("Feasibility scenario cannot cross companies.")
    data.setdefault("currency_code", company.currency)
    data.setdefault("created_by_public_id", actor_public_id)
    data["projected_margin_percent"] = _calculate_margin(data)
    return _create(FeasibilityScenario, company=company, parcel=parcel, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.feasibility.created", **data)


@transaction.atomic
def transition_feasibility(*, scenario: FeasibilityScenario, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> FeasibilityScenario:
    scenario = FeasibilityScenario.objects.select_for_update().get(pk=scenario.pk)
    status_code = status_code.strip().upper()
    if scenario.version != expected_version:
        raise ValidationError("Feasibility scenario changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "REJECTED": {"DRAFT"},
        "APPROVED": {"SUPERSEDED"},
        "SUPERSEDED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(scenario.status_code, set()):
        raise ValidationError(f"Invalid feasibility transition from {scenario.status_code} to {status_code}.")
    if status_code == "APPROVED" and scenario.created_by_public_id == actor_public_id:
        raise ValidationError("The feasibility creator cannot approve the same scenario.")
    policy = LandPolicyVersion.objects.filter(company=scenario.company).order_by("-version").first()
    if status_code == "APPROVED" and policy and scenario.projected_margin_percent < policy.minimum_margin_percent and not note.strip():
        raise ValidationError("Approval below the configured margin threshold requires a decision note.")
    before = {"status": scenario.status_code, "version": scenario.version}
    scenario.status_code = status_code
    scenario.decision_note = note
    scenario.approved_by_public_id = actor_public_id if status_code == "APPROVED" else None
    scenario.approved_at = timezone.now() if status_code == "APPROVED" else None
    scenario.version += 1
    scenario.full_clean()
    scenario.save()
    _record(company=scenario.company, action="TRANSITION", event_type="land.feasibility.transitioned", entity_type="FeasibilityScenario", entity_public_id=scenario.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=scenario.version, before=before, after={"status": scenario.status_code, "projected_margin_percent": str(scenario.projected_margin_percent), "note": note})
    return scenario


@transaction.atomic
def create_opportunity(*, company: Company, parcel: LandParcel, feasibility: FeasibilityScenario | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> AcquisitionOpportunity:
    if parcel.company_id != company.id:
        raise ValidationError("Acquisition opportunity cannot cross companies.")
    if feasibility and (feasibility.company_id != company.id or feasibility.parcel_id != parcel.id):
        raise ValidationError("Acquisition feasibility must belong to the same parcel and company.")
    data.setdefault("currency_code", company.currency)
    data.setdefault("owner_public_id", actor_public_id)
    return _create(AcquisitionOpportunity, company=company, parcel=parcel, feasibility=feasibility, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.opportunity.created", **data)


@transaction.atomic
def transition_opportunity(*, opportunity: AcquisitionOpportunity, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> AcquisitionOpportunity:
    opportunity = AcquisitionOpportunity.objects.select_for_update(of=("self",)).select_related("feasibility", "parcel").get(pk=opportunity.pk)
    status_code = status_code.strip().upper()
    if opportunity.version != expected_version:
        raise ValidationError("Acquisition opportunity changed. Refresh and retry.")
    allowed = {
        "IDENTIFIED": {"SCREENING", "DROPPED"},
        "SCREENING": {"DUE_DILIGENCE", "ON_HOLD", "DROPPED"},
        "DUE_DILIGENCE": {"NEGOTIATION", "ON_HOLD", "DROPPED"},
        "NEGOTIATION": {"APPROVED", "ON_HOLD", "DROPPED"},
        "APPROVED": {"ACQUIRED", "ON_HOLD", "DROPPED"},
        "ON_HOLD": {"SCREENING", "DUE_DILIGENCE", "NEGOTIATION", "DROPPED"},
        "ACQUIRED": {"CLOSED"},
        "CLOSED": set(),
        "DROPPED": set(),
    }
    if status_code not in allowed.get(opportunity.stage_code, set()):
        raise ValidationError(f"Invalid acquisition transition from {opportunity.stage_code} to {status_code}.")
    if status_code in {"NEGOTIATION", "APPROVED"}:
        if opportunity.feasibility is None or opportunity.feasibility.status_code != "APPROVED":
            raise ValidationError("An approved feasibility scenario is required before negotiation or acquisition approval.")
        uncleared = DueDiligenceCase.objects.filter(company=opportunity.company, parcel=opportunity.parcel).exclude(status_code__in=["CLEARED", "CONDITIONAL", "CANCELLED"]).exists()
        if uncleared:
            raise ValidationError("All active due-diligence cases must reach a governed decision before negotiation or approval.")
    if status_code == "APPROVED":
        if opportunity.owner_public_id == actor_public_id:
            raise ValidationError("The acquisition opportunity owner cannot independently approve the same opportunity.")
        critical_risk = LandRisk.objects.filter(company=opportunity.company, opportunity=opportunity, severity_code="CRITICAL").exclude(status_code__in=["CLOSED", "ACCEPTED"]).exists()
        if critical_risk:
            raise ValidationError("Critical land risks must be closed or formally accepted before acquisition approval.")
    if status_code == "ACQUIRED":
        accepted_offer = CommercialOffer.objects.filter(company=opportunity.company, opportunity=opportunity, status_code="ACCEPTED").exists()
        if not accepted_offer:
            raise ValidationError("An accepted commercial offer is required before marking the land acquired.")
        missing_approval = StatutoryApproval.objects.filter(company=opportunity.company, opportunity=opportunity, mandatory_for_acquisition=True).exclude(status_code="APPROVED").exists()
        if missing_approval:
            raise ValidationError("All mandatory acquisition approvals must be approved before acquisition completion.")
    before = {"stage": opportunity.stage_code, "version": opportunity.version}
    opportunity.stage_code = status_code
    if status_code == "ACQUIRED":
        opportunity.parcel.status_code = "ACQUIRED"
        opportunity.parcel.version += 1
        opportunity.parcel.save(update_fields=["status_code", "version", "updated_at"])
    opportunity.version += 1
    opportunity.full_clean()
    opportunity.save()
    _record(company=opportunity.company, action="TRANSITION", event_type="land.opportunity.transitioned", entity_type="AcquisitionOpportunity", entity_public_id=opportunity.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=opportunity.version, before=before, after={"stage": opportunity.stage_code, "note": note})
    create_event(company=opportunity.company, opportunity=opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event_type_code="STAGE_CHANGE", event_on=timezone.now(), summary=f"Opportunity moved to {status_code}. {note}".strip(), evidence={"from": before["stage"], "to": status_code})
    return opportunity


@transaction.atomic
def create_offer(*, company: Company, opportunity: AcquisitionOpportunity, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> CommercialOffer:
    if opportunity.company_id != company.id:
        raise ValidationError("Commercial offer cannot cross companies.")
    if opportunity.stage_code not in {"NEGOTIATION", "APPROVED"}:
        raise ValidationError("Commercial offers may be created only during negotiation or acquisition approval.")
    data.setdefault("currency_code", opportunity.currency_code or company.currency)
    data.setdefault("created_by_public_id", actor_public_id)
    return _create(CommercialOffer, company=company, opportunity=opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.offer.created", **data)


@transaction.atomic
def transition_offer(*, offer: CommercialOffer, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> CommercialOffer:
    offer = CommercialOffer.objects.select_for_update().select_related("opportunity").get(pk=offer.pk)
    status_code = status_code.strip().upper()
    if offer.version != expected_version:
        raise ValidationError("Commercial offer changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"SUBMITTED", "WITHDRAWN"},
        "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
        "APPROVED": {"ISSUED", "WITHDRAWN"},
        "ISSUED": {"ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"},
        "REJECTED": {"DRAFT"},
        "ACCEPTED": set(),
        "EXPIRED": set(),
        "WITHDRAWN": set(),
    }
    if status_code not in allowed.get(offer.status_code, set()):
        raise ValidationError(f"Invalid offer transition from {offer.status_code} to {status_code}.")
    if status_code == "APPROVED" and offer.created_by_public_id == actor_public_id:
        raise ValidationError("The offer creator cannot approve the same commercial offer.")
    if status_code == "ACCEPTED":
        competing = CommercialOffer.objects.select_for_update().filter(company=offer.company, opportunity=offer.opportunity, status_code="ACCEPTED").exclude(pk=offer.pk).exists()
        if competing:
            raise ValidationError("The opportunity already has an accepted commercial offer.")
    before = {"status": offer.status_code, "version": offer.version}
    offer.status_code = status_code
    offer.decision_note = note
    if status_code == "APPROVED":
        offer.approved_by_public_id = actor_public_id
        offer.approved_at = timezone.now()
    if status_code == "ISSUED":
        offer.issued_at = timezone.now()
    if status_code == "ACCEPTED":
        offer.accepted_at = timezone.now()
    offer.version += 1
    offer.full_clean()
    offer.save()
    _record(company=offer.company, action="TRANSITION", event_type="land.offer.transitioned", entity_type="CommercialOffer", entity_public_id=offer.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=offer.version, before=before, after={"status": offer.status_code, "amount": str(offer.amount), "currency": offer.currency_code, "note": note})
    create_event(company=offer.company, opportunity=offer.opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event_type_code="OFFER_STATUS", event_on=timezone.now(), summary=f"Offer {offer.offer_number} moved to {status_code}.", evidence={"amount": str(offer.amount), "currency": offer.currency_code})
    return offer


@transaction.atomic
def create_approval(*, company: Company, parcel: LandParcel, opportunity: AcquisitionOpportunity | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> StatutoryApproval:
    if parcel.company_id != company.id:
        raise ValidationError("Statutory approval cannot cross companies.")
    if opportunity and (opportunity.company_id != company.id or opportunity.parcel_id != parcel.id):
        raise ValidationError("Approval opportunity must belong to the same company and parcel.")
    data.setdefault("owner_public_id", actor_public_id)
    return _create(StatutoryApproval, company=company, parcel=parcel, opportunity=opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.approval.created", **data)


@transaction.atomic
def transition_approval(*, approval: StatutoryApproval, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> StatutoryApproval:
    approval = StatutoryApproval.objects.select_for_update().get(pk=approval.pk)
    status_code = status_code.strip().upper()
    if approval.version != expected_version:
        raise ValidationError("Statutory approval changed. Refresh and retry.")
    allowed = {
        "PLANNED": {"SUBMITTED", "CANCELLED"},
        "SUBMITTED": {"UNDER_REVIEW", "APPROVED", "REJECTED", "WITHDRAWN"},
        "UNDER_REVIEW": {"APPROVED", "REJECTED", "WITHDRAWN"},
        "APPROVED": {"EXPIRED", "SUPERSEDED"},
        "REJECTED": {"PLANNED"},
        "EXPIRED": {"PLANNED"},
        "WITHDRAWN": {"PLANNED"},
        "SUPERSEDED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(approval.status_code, set()):
        raise ValidationError(f"Invalid statutory-approval transition from {approval.status_code} to {status_code}.")
    if status_code == "APPROVED" and approval.owner_public_id == actor_public_id:
        raise ValidationError("The statutory approval owner cannot independently approve the same approval record.")
    before = {"status": approval.status_code, "version": approval.version}
    approval.status_code = status_code
    today = timezone.localdate()
    if status_code == "SUBMITTED" and approval.submitted_on is None:
        approval.submitted_on = today
    if status_code == "APPROVED" and approval.approved_on is None:
        approval.approved_on = today
    if note:
        conditions = dict(approval.conditions)
        conditions["latest_decision_note"] = note
        approval.conditions = conditions
    approval.version += 1
    approval.full_clean()
    approval.save()
    _record(company=approval.company, action="TRANSITION", event_type="land.approval.transitioned", entity_type="StatutoryApproval", entity_public_id=approval.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=approval.version, before=before, after={"status": approval.status_code, "note": note})
    return approval


@transaction.atomic
def create_risk(*, company: Company, parcel: LandParcel, opportunity: AcquisitionOpportunity | None, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> LandRisk:
    if parcel.company_id != company.id:
        raise ValidationError("Land risk cannot cross companies.")
    if opportunity and (opportunity.company_id != company.id or opportunity.parcel_id != parcel.id):
        raise ValidationError("Risk opportunity must belong to the same company and parcel.")
    data.setdefault("owner_public_id", actor_public_id)
    return _create(LandRisk, company=company, parcel=parcel, opportunity=opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.risk.created", **data)


@transaction.atomic
def transition_risk(*, risk: LandRisk, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, note: str = "") -> LandRisk:
    risk = LandRisk.objects.select_for_update().get(pk=risk.pk)
    status_code = status_code.strip().upper()
    if risk.version != expected_version:
        raise ValidationError("Land risk changed. Refresh and retry.")
    allowed = {
        "OPEN": {"MITIGATING", "ACCEPTED", "CLOSED"},
        "MITIGATING": {"OPEN", "ACCEPTED", "CLOSED"},
        "ACCEPTED": {"MITIGATING", "CLOSED"},
        "CLOSED": {"OPEN"},
    }
    if status_code not in allowed.get(risk.status_code, set()):
        raise ValidationError(f"Invalid risk transition from {risk.status_code} to {status_code}.")
    if status_code in {"ACCEPTED", "CLOSED"} and not note.strip():
        raise ValidationError("Risk acceptance or closure requires a governance note.")
    before = {"status": risk.status_code, "version": risk.version}
    risk.status_code = status_code
    if status_code == "ACCEPTED":
        risk.accepted_by_public_id = actor_public_id
        risk.accepted_at = timezone.now()
    if status_code == "CLOSED":
        risk.closed_by_public_id = actor_public_id
        risk.closed_at = timezone.now()
    if note:
        risk.mitigation_plan = f"{risk.mitigation_plan}\n{note}".strip()
    risk.version += 1
    risk.full_clean()
    risk.save()
    _record(company=risk.company, action="TRANSITION", event_type="land.risk.transitioned", entity_type="LandRisk", entity_public_id=risk.public_id, actor_public_id=actor_public_id, correlation_id=correlation_id, version=risk.version, before=before, after={"status": risk.status_code, "note": note})
    return risk


@transaction.atomic
def create_event(*, company: Company, opportunity: AcquisitionOpportunity, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any) -> AcquisitionEvent:
    if opportunity.company_id != company.id:
        raise ValidationError("Acquisition event cannot cross companies.")
    data.setdefault("recorded_by_public_id", actor_public_id)
    return _create(AcquisitionEvent, company=company, opportunity=opportunity, actor_public_id=actor_public_id, correlation_id=correlation_id, event="land.acquisition.event.recorded", **data)
