from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.sustainabilityops.models import (
    AssuranceAssessment,
    CarbonActivity,
    CarbonInventory,
    DisclosureReport,
    EmissionFactor,
    ESGInitiative,
    ResourceConsumption,
    SustainabilityPolicyVersion,
    SustainabilityTarget,
    WasteMovement,
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
    _, created = SustainabilityPolicyVersion.objects.get_or_create(
        company=company,
        version=1,
        defaults={
            "status_code": "DRAFT",
            "organizational_boundary_code": "OPERATIONAL_CONTROL",
            "reporting_frequency_code": "MONTHLY",
            "configuration": {
                "phase": 38,
                "release": "sustainability-esg-carbon-operations",
                "factor_governance": "TENANT_CONFIGURED",
                "do_not_mix_units": True,
            },
        },
    )
    return {"policy": int(created)}


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
    version = getattr(item, "version", 1)
    code = getattr(item, "code", str(item.public_id))
    _record(
        company=company,
        action="CREATE",
        event_type=event,
        entity_type=model.__name__,
        entity_public_id=item.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=version,
        after={"code": code, "status": getattr(item, "status_code", "RECORDED")},
    )
    return item


@transaction.atomic
def create_factor(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> EmissionFactor:
    return _create(
        EmissionFactor,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.factor.created",
        **data,
    )


@transaction.atomic
def record_activity(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, factor: EmissionFactor, **data: Any
) -> CarbonActivity:
    data.setdefault("captured_by_public_id", actor_public_id)
    data.setdefault("activity_unit_code", factor.activity_unit_code)
    quantity = Decimal(data["quantity"])
    data["calculated_kg_co2e"] = (quantity * factor.factor_kg_co2e_per_unit).quantize(Decimal("0.0001"))
    return _create(
        CarbonActivity,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.activity.recorded",
        factor=factor,
        **data,
    )


@transaction.atomic
def transition_activity(
    *,
    activity: CarbonActivity,
    status_code: str,
    expected_version: int,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> CarbonActivity:
    activity = CarbonActivity.objects.select_for_update().get(pk=activity.pk)
    if activity.version != expected_version:
        raise ValidationError("Carbon activity changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"VERIFIED", "REJECTED"},
        "REJECTED": {"DRAFT"},
        "VERIFIED": {"REJECTED"},
    }
    if status_code not in allowed.get(activity.status_code, set()):
        raise ValidationError(f"Invalid activity transition from {activity.status_code} to {status_code}.")
    if status_code == "VERIFIED" and activity.captured_by_public_id == actor_public_id:
        raise ValidationError("The activity recorder cannot verify the same carbon activity.")
    before = {"status": activity.status_code, "version": activity.version}
    activity.status_code = status_code
    if status_code == "VERIFIED":
        activity.verified_by_public_id = actor_public_id
        activity.verified_at = timezone.now()
    elif status_code == "DRAFT":
        activity.verified_by_public_id = None
        activity.verified_at = None
    activity.version += 1
    activity.full_clean()
    activity.save()
    _record(
        company=activity.company,
        action="TRANSITION",
        event_type="sustainability.activity.transitioned",
        entity_type="CarbonActivity",
        entity_public_id=activity.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=activity.version,
        before=before,
        after={"status": status_code, "kg_co2e": str(activity.calculated_kg_co2e)},
    )
    return activity


@transaction.atomic
def create_inventory(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> CarbonInventory:
    period_start = data["period_start"]
    period_end = data["period_end"]
    aggregates = (
        CarbonActivity.objects.filter(
            company=company,
            status_code="VERIFIED",
            activity_date__gte=period_start,
            activity_date__lte=period_end,
        )
        .values("factor__scope_code")
        .annotate(total=Sum("calculated_kg_co2e"), rows=Count("id"))
    )
    scope_totals = {"SCOPE_1": Decimal("0"), "SCOPE_2": Decimal("0"), "SCOPE_3": Decimal("0")}
    activity_count = 0
    for row in aggregates:
        scope = row["factor__scope_code"]
        if scope in scope_totals:
            scope_totals[scope] = row["total"] or Decimal("0")
        activity_count += row["rows"] or 0
    offsets = Decimal(data.get("offsets_kg_co2e", Decimal("0")))
    gross = sum(scope_totals.values(), Decimal("0"))
    data.update(
        {
            "scope1_kg_co2e": scope_totals["SCOPE_1"],
            "scope2_kg_co2e": scope_totals["SCOPE_2"],
            "scope3_kg_co2e": scope_totals["SCOPE_3"],
            "net_kg_co2e": max(gross - offsets, Decimal("0")),
            "activity_count": activity_count,
            "prepared_by_public_id": actor_public_id,
        }
    )
    return _create(
        CarbonInventory,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.inventory.created",
        **data,
    )


@transaction.atomic
def transition_inventory(
    *, inventory: CarbonInventory, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> CarbonInventory:
    inventory = CarbonInventory.objects.select_for_update().get(pk=inventory.pk)
    if inventory.version != expected_version:
        raise ValidationError("Carbon inventory changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"IN_REVIEW", "CANCELLED"},
        "IN_REVIEW": {"APPROVED", "DRAFT", "CANCELLED"},
        "APPROVED": {"PUBLISHED", "IN_REVIEW"},
        "PUBLISHED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(inventory.status_code, set()):
        raise ValidationError(f"Invalid inventory transition from {inventory.status_code} to {status_code}.")
    if status_code == "APPROVED" and inventory.prepared_by_public_id == actor_public_id:
        raise ValidationError("The inventory preparer cannot approve the same carbon inventory.")
    before = {"status": inventory.status_code, "version": inventory.version}
    if status_code == "APPROVED":
        inventory.approved_by_public_id = actor_public_id
    if status_code == "PUBLISHED":
        if inventory.approved_by_public_id is None:
            raise ValidationError("Carbon inventory must be independently approved before publication.")
        inventory.published_at = timezone.now()
    inventory.status_code = status_code
    inventory.version += 1
    inventory.full_clean()
    inventory.save()
    _record(
        company=inventory.company,
        action="TRANSITION",
        event_type="sustainability.inventory.transitioned",
        entity_type="CarbonInventory",
        entity_public_id=inventory.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=inventory.version,
        before=before,
        after={"code": inventory.code, "status": status_code, "net_kg_co2e": str(inventory.net_kg_co2e)},
    )
    return inventory


@transaction.atomic
def record_resource(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ResourceConsumption:
    data.setdefault("captured_by_public_id", actor_public_id)
    data.setdefault("currency", company.currency)
    return _create(
        ResourceConsumption,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.resource.recorded",
        **data,
    )


@transaction.atomic
def record_waste(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> WasteMovement:
    data.setdefault("captured_by_public_id", actor_public_id)
    return _create(
        WasteMovement,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.waste.recorded",
        **data,
    )


@transaction.atomic
def create_target(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> SustainabilityTarget:
    return _create(
        SustainabilityTarget,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.target.created",
        **data,
    )


@transaction.atomic
def transition_target(
    *, target: SustainabilityTarget, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
    latest_value: Decimal | None = None, progress_percent: Decimal | None = None,
) -> SustainabilityTarget:
    target = SustainabilityTarget.objects.select_for_update().get(pk=target.pk)
    if target.version != expected_version:
        raise ValidationError("Sustainability target changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"ACTIVE", "CANCELLED"},
        "ACTIVE": {"AT_RISK", "ACHIEVED", "CANCELLED"},
        "AT_RISK": {"ACTIVE", "ACHIEVED", "CANCELLED"},
        "ACHIEVED": {"ACTIVE"},
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(target.status_code, set()):
        raise ValidationError(f"Invalid target transition from {target.status_code} to {status_code}.")
    before = {"status": target.status_code, "version": target.version}
    if latest_value is not None:
        target.latest_value = latest_value
    if progress_percent is not None:
        target.progress_percent = progress_percent
    target.status_code = status_code
    target.version += 1
    target.full_clean()
    target.save()
    _record(
        company=target.company,
        action="TRANSITION",
        event_type="sustainability.target.transitioned",
        entity_type="SustainabilityTarget",
        entity_public_id=target.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=target.version,
        before=before,
        after={"code": target.code, "status": status_code, "progress_percent": str(target.progress_percent)},
    )
    return target


@transaction.atomic
def create_initiative(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> ESGInitiative:
    data.setdefault("currency", company.currency)
    return _create(
        ESGInitiative,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.initiative.created",
        **data,
    )


@transaction.atomic
def transition_initiative(
    *, initiative: ESGInitiative, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID,
    realized_value: Decimal | None = None,
) -> ESGInitiative:
    initiative = ESGInitiative.objects.select_for_update().get(pk=initiative.pk)
    if initiative.version != expected_version:
        raise ValidationError("ESG initiative changed. Refresh and retry.")
    allowed = {
        "PLANNED": {"IN_PROGRESS", "CANCELLED"},
        "IN_PROGRESS": {"BLOCKED", "COMPLETED", "CANCELLED"},
        "BLOCKED": {"IN_PROGRESS", "COMPLETED", "CANCELLED"},
        "COMPLETED": {"IN_PROGRESS"},
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(initiative.status_code, set()):
        raise ValidationError(f"Invalid initiative transition from {initiative.status_code} to {status_code}.")
    before = {"status": initiative.status_code, "version": initiative.version}
    if realized_value is not None:
        initiative.realized_value = realized_value
    initiative.status_code = status_code
    initiative.completed_at = timezone.now() if status_code == "COMPLETED" else None
    initiative.version += 1
    initiative.full_clean()
    initiative.save()
    _record(
        company=initiative.company,
        action="TRANSITION",
        event_type="sustainability.initiative.transitioned",
        entity_type="ESGInitiative",
        entity_public_id=initiative.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=initiative.version,
        before=before,
        after={"code": initiative.code, "status": status_code, "realized_value": str(initiative.realized_value)},
    )
    return initiative


@transaction.atomic
def create_assessment(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> AssuranceAssessment:
    data.setdefault("prepared_by_public_id", actor_public_id)
    return _create(
        AssuranceAssessment,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.assessment.created",
        **data,
    )


@transaction.atomic
def transition_assessment(
    *, assessment: AssuranceAssessment, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> AssuranceAssessment:
    assessment = AssuranceAssessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.version != expected_version:
        raise ValidationError("Assurance assessment changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"IN_REVIEW", "CANCELLED"},
        "IN_REVIEW": {"APPROVED", "DRAFT", "CANCELLED"},
        "APPROVED": {"PUBLISHED", "IN_REVIEW"},
        "PUBLISHED": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(assessment.status_code, set()):
        raise ValidationError(f"Invalid assessment transition from {assessment.status_code} to {status_code}.")
    if status_code == "APPROVED" and assessment.prepared_by_public_id == actor_public_id:
        raise ValidationError("The assessment preparer cannot approve the same assurance record.")
    before = {"status": assessment.status_code, "version": assessment.version}
    if status_code == "APPROVED":
        assessment.approved_by_public_id = actor_public_id
    if status_code == "PUBLISHED":
        if assessment.approved_by_public_id is None:
            raise ValidationError("Assurance assessment must be approved before publication.")
        assessment.published_at = timezone.now()
    assessment.status_code = status_code
    assessment.version += 1
    assessment.full_clean()
    assessment.save()
    _record(
        company=assessment.company,
        action="TRANSITION",
        event_type="sustainability.assessment.transitioned",
        entity_type="AssuranceAssessment",
        entity_public_id=assessment.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=assessment.version,
        before=before,
        after={"code": assessment.code, "status": status_code, "major_findings": assessment.major_findings},
    )
    return assessment


@transaction.atomic
def create_disclosure(
    *, company: Company, actor_public_id: uuid.UUID, correlation_id: uuid.UUID, **data: Any
) -> DisclosureReport:
    data.setdefault("prepared_by_public_id", actor_public_id)
    return _create(
        DisclosureReport,
        company=company,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        event="sustainability.disclosure.created",
        **data,
    )


@transaction.atomic
def transition_disclosure(
    *, disclosure: DisclosureReport, status_code: str, expected_version: int, actor_public_id: uuid.UUID, correlation_id: uuid.UUID
) -> DisclosureReport:
    disclosure = DisclosureReport.objects.select_for_update().get(pk=disclosure.pk)
    if disclosure.version != expected_version:
        raise ValidationError("Disclosure report changed. Refresh and retry.")
    allowed = {
        "DRAFT": {"IN_REVIEW", "CANCELLED"},
        "IN_REVIEW": {"APPROVED", "DRAFT", "CANCELLED"},
        "APPROVED": {"PUBLISHED", "IN_REVIEW"},
        "PUBLISHED": {"ARCHIVED"},
        "ARCHIVED": set(),
        "CANCELLED": set(),
    }
    if status_code not in allowed.get(disclosure.status_code, set()):
        raise ValidationError(f"Invalid disclosure transition from {disclosure.status_code} to {status_code}.")
    if status_code == "APPROVED" and disclosure.prepared_by_public_id == actor_public_id:
        raise ValidationError("The report preparer cannot approve the same disclosure report.")
    before = {"status": disclosure.status_code, "version": disclosure.version}
    if status_code == "APPROVED":
        disclosure.approved_by_public_id = actor_public_id
    if status_code == "PUBLISHED":
        if disclosure.approved_by_public_id is None:
            raise ValidationError("Disclosure report must be approved before publication.")
        disclosure.published_at = timezone.now()
    disclosure.status_code = status_code
    disclosure.version += 1
    disclosure.full_clean()
    disclosure.save()
    _record(
        company=disclosure.company,
        action="TRANSITION",
        event_type="sustainability.disclosure.transitioned",
        entity_type="DisclosureReport",
        entity_public_id=disclosure.public_id,
        actor_public_id=actor_public_id,
        correlation_id=correlation_id,
        version=disclosure.version,
        before=before,
        after={"code": disclosure.code, "status": status_code, "framework": disclosure.framework_code},
    )
    return disclosure
