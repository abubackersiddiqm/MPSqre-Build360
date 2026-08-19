from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from modules.estimation.models import (
    BoqItem,
    BoqSection,
    Estimate,
    EstimateBaseline,
    EstimateVersion,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.projects.application.services import initial_stage, resolve_stage
from modules.projects.models import DeliveryStage, Project
from modules.tenant.models import Company

MONEY_QUANTUM = Decimal("0.0001")


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
            before=before or {},
            after=after or {},
            reason_code=reason_code,
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


def _recalculate(version: EstimateVersion) -> None:
    totals = BoqItem.objects.filter(
        company=version.company,
        estimate_version=version,
    ).aggregate(
        subtotal=Sum("amount"),
        tax_total=Sum("tax_amount"),
        grand_total=Sum("total_amount"),
    )
    version.subtotal = totals["subtotal"] or Decimal("0")
    version.tax_total = totals["tax_total"] or Decimal("0")
    version.grand_total = totals["grand_total"] or Decimal("0")
    version.version += 1
    version.save(
        update_fields=["subtotal", "tax_total", "grand_total", "version", "updated_at"]
    )


@transaction.atomic
def create_estimate(
    *,
    company: Company,
    actor: RequestActor,
    project_public_id: uuid.UUID,
    code: str,
    name: str,
    currency: str | None = None,
    notes: str = "",
) -> tuple[Estimate, EstimateVersion]:
    project = _project(company, project_public_id)
    estimate = Estimate(
        company=company,
        project=project,
        code=code.strip().upper(),
        name=name.strip(),
        currency=(currency or project.currency).upper(),
        created_by_public_id=actor.user_public_id,
        active_version_number=1,
    )
    estimate.full_clean()
    estimate.save()
    version = EstimateVersion(
        company=company,
        estimate=estimate,
        version_number=1,
        stage=initial_stage(company, DeliveryStage.EntityType.ESTIMATE_VERSION),
        notes=notes.strip(),
        created_by_public_id=actor.user_public_id,
    )
    version.full_clean()
    version.save()
    _audit(
        actor=actor,
        company=company,
        action="estimation.estimate.created",
        entity_type="estimate",
        entity_public_id=estimate.public_id,
        after={
            "project_public_id": str(project.public_id),
            "code": estimate.code,
            "version_number": 1,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="estimation.estimate_created",
        aggregate_type="estimate",
        aggregate_public_id=estimate.public_id,
        aggregate_version=estimate.version,
        payload={"project_public_id": str(project.public_id), "version_number": 1},
    )
    return estimate, version


@transaction.atomic
def create_estimate_version(
    *,
    company: Company,
    actor: RequestActor,
    estimate_public_id: uuid.UUID,
    source_version_public_id: uuid.UUID | None = None,
    notes: str = "",
) -> EstimateVersion:
    estimate = Estimate.objects.select_for_update().filter(
        company=company,
        public_id=estimate_public_id,
    ).first()
    if estimate is None:
        raise ValidationError("Estimate was not found")
    latest = (
        EstimateVersion.objects.filter(company=company, estimate=estimate)
        .order_by("-version_number")
        .first()
    )
    next_number = 1 if latest is None else latest.version_number + 1
    source = None
    if source_version_public_id:
        source = EstimateVersion.objects.filter(
            company=company,
            estimate=estimate,
            public_id=source_version_public_id,
        ).first()
        if source is None:
            raise ValidationError("Source estimate version was not found")
    version = EstimateVersion(
        company=company,
        estimate=estimate,
        version_number=next_number,
        stage=initial_stage(company, DeliveryStage.EntityType.ESTIMATE_VERSION),
        notes=notes.strip(),
        created_by_public_id=actor.user_public_id,
    )
    version.full_clean()
    version.save()
    if source:
        section_map: dict[int, BoqSection] = {}
        for section in source.sections.order_by("sort_order"):
            copy = BoqSection.objects.create(
                company=company,
                estimate_version=version,
                code=section.code,
                name=section.name,
                sort_order=section.sort_order,
            )
            section_map[section.pk] = copy
        BoqItem.objects.bulk_create(
            [
                BoqItem(
                    company=company,
                    estimate_version=version,
                    section=section_map.get(item.section_id),
                    item_code=item.item_code,
                    description=item.description,
                    unit_code=item.unit_code,
                    quantity=item.quantity,
                    rate=item.rate,
                    amount=item.amount,
                    tax_rate_percent=item.tax_rate_percent,
                    tax_amount=item.tax_amount,
                    total_amount=item.total_amount,
                    sort_order=item.sort_order,
                )
                for item in source.items.order_by("sort_order", "item_code")
            ]
        )
        _recalculate(version)
    estimate.active_version_number = next_number
    estimate.version += 1
    estimate.save(update_fields=["active_version_number", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="estimation.version.created",
        entity_type="estimate_version",
        entity_public_id=version.public_id,
        after={"estimate_public_id": str(estimate.public_id), "version_number": next_number},
    )
    _event(
        actor=actor,
        company=company,
        event_type="estimation.version_created",
        aggregate_type="estimate_version",
        aggregate_public_id=version.public_id,
        aggregate_version=version.version,
        payload={"estimate_public_id": str(estimate.public_id), "version_number": next_number},
    )
    return version


@transaction.atomic
def create_section(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    code: str,
    name: str,
    sort_order: int = 100,
) -> BoqSection:
    version = EstimateVersion.objects.filter(
        company=company,
        public_id=version_public_id,
    ).first()
    if version is None:
        raise ValidationError("Estimate version was not found")
    if version.baselined_at:
        raise ValidationError("A baselined estimate version is immutable")
    section = BoqSection(
        company=company,
        estimate_version=version,
        code=code.strip().upper(),
        name=name.strip(),
        sort_order=sort_order,
    )
    section.full_clean()
    section.save()
    _audit(
        actor=actor,
        company=company,
        action="estimation.section.created",
        entity_type="boq_section",
        entity_public_id=section.public_id,
        after={"estimate_version_public_id": str(version.public_id), "code": section.code},
    )
    return section


@transaction.atomic
def create_boq_item(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    item_code: str,
    description: str,
    unit_code: str,
    quantity: Decimal,
    rate: Decimal,
    tax_rate_percent: Decimal = Decimal("0"),
    section_public_id: uuid.UUID | None = None,
    sort_order: int = 100,
) -> BoqItem:
    version = EstimateVersion.objects.select_for_update().filter(
        company=company,
        public_id=version_public_id,
    ).first()
    if version is None:
        raise ValidationError("Estimate version was not found")
    if version.baselined_at:
        raise ValidationError("A baselined estimate version is immutable")
    section = None
    if section_public_id:
        section = BoqSection.objects.filter(
            company=company,
            estimate_version=version,
            public_id=section_public_id,
        ).first()
        if section is None:
            raise ValidationError("BOQ section was not found")
    amount = (quantity * rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    tax_amount = (
        amount * tax_rate_percent / Decimal("100")
    ).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    item = BoqItem(
        company=company,
        estimate_version=version,
        section=section,
        item_code=item_code.strip().upper(),
        description=description.strip(),
        unit_code=unit_code.strip().upper(),
        quantity=quantity,
        rate=rate,
        amount=amount,
        tax_rate_percent=tax_rate_percent,
        tax_amount=tax_amount,
        total_amount=amount + tax_amount,
        sort_order=sort_order,
    )
    item.full_clean()
    item.save()
    _recalculate(version)
    _audit(
        actor=actor,
        company=company,
        action="estimation.boq_item.created",
        entity_type="boq_item",
        entity_public_id=item.public_id,
        after={
            "estimate_version_public_id": str(version.public_id),
            "item_code": item.item_code,
            "total_amount": str(item.total_amount),
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="estimation.boq_item_created",
        aggregate_type="boq_item",
        aggregate_public_id=item.public_id,
        aggregate_version=item.version,
        payload={"estimate_version_public_id": str(version.public_id)},
    )
    return item


@transaction.atomic
def transition_estimate_version(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> EstimateVersion:
    version = (
        EstimateVersion.objects.select_for_update()
        .select_related("stage", "estimate")
        .filter(company=company, public_id=version_public_id)
        .first()
    )
    if version is None:
        raise ValidationError("Estimate version was not found")
    if version.version != expected_version:
        raise ValidationError("Estimate version has changed; refresh before retrying")
    if version.baselined_at:
        raise ValidationError("A baselined estimate version is immutable")
    target = resolve_stage(
        company,
        target_stage_public_id,
        DeliveryStage.EntityType.ESTIMATE_VERSION,
    )
    if target.code not in version.stage.allowed_next_codes:
        raise ValidationError("The requested estimate transition is not permitted")
    old_code = version.stage.code
    now = timezone.now()
    version.stage = target
    version.version += 1
    if target.outcome == DeliveryStage.Outcome.REVIEW:
        version.submitted_at = now
    elif target.outcome == DeliveryStage.Outcome.APPROVED:
        version.approved_at = now
    elif target.outcome == DeliveryStage.Outcome.SUPERSEDED:
        version.superseded_at = now
    version.full_clean()
    version.save()
    _audit(
        actor=actor,
        company=company,
        action="estimation.version.transitioned",
        entity_type="estimate_version",
        entity_public_id=version.public_id,
        before={"stage": old_code, "version": expected_version},
        after={"stage": target.code, "version": version.version},
        reason_code=reason_code.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="estimation.version_transitioned",
        aggregate_type="estimate_version",
        aggregate_public_id=version.public_id,
        aggregate_version=version.version,
        payload={"from": old_code, "to": target.code},
    )
    return version


@transaction.atomic
def baseline_estimate_version(
    *,
    company: Company,
    actor: RequestActor,
    version_public_id: uuid.UUID,
    expected_version: int,
) -> EstimateBaseline:
    version = (
        EstimateVersion.objects.select_for_update()
        .select_related("stage", "estimate", "estimate__project")
        .filter(company=company, public_id=version_public_id)
        .first()
    )
    if version is None:
        raise ValidationError("Estimate version was not found")
    if version.version != expected_version:
        raise ValidationError("Estimate version has changed; refresh before retrying")
    if version.baselined_at:
        existing = EstimateBaseline.objects.filter(
            company=company,
            estimate_version=version,
        ).first()
        if existing is None:
            raise ValidationError("Estimate baseline state is inconsistent")
        return existing
    if not version.stage.allows_baseline:
        raise ValidationError("The current estimate stage does not allow baselining")
    sections = [
        {
            "public_id": str(section.public_id),
            "code": section.code,
            "name": section.name,
            "sort_order": section.sort_order,
        }
        for section in version.sections.order_by("sort_order", "code")
    ]
    items = [
        {
            "public_id": str(item.public_id),
            "section_public_id": str(item.section.public_id) if item.section else None,
            "item_code": item.item_code,
            "description": item.description,
            "unit_code": item.unit_code,
            "quantity": str(item.quantity),
            "rate": str(item.rate),
            "amount": str(item.amount),
            "tax_rate_percent": str(item.tax_rate_percent),
            "tax_amount": str(item.tax_amount),
            "total_amount": str(item.total_amount),
            "sort_order": item.sort_order,
        }
        for item in version.items.select_related("section").order_by("sort_order", "item_code")
    ]
    baseline = EstimateBaseline.objects.create(
        company=company,
        estimate=version.estimate,
        estimate_version=version,
        snapshot={
            "estimate": {
                "public_id": str(version.estimate.public_id),
                "project_public_id": str(version.estimate.project.public_id),
                "code": version.estimate.code,
                "name": version.estimate.name,
                "currency": version.estimate.currency,
            },
            "version": {
                "public_id": str(version.public_id),
                "version_number": version.version_number,
                "stage": version.stage.code,
                "subtotal": str(version.subtotal),
                "tax_total": str(version.tax_total),
                "grand_total": str(version.grand_total),
            },
            "sections": sections,
            "items": items,
        },
        created_by_public_id=actor.user_public_id,
    )
    version.baselined_at = timezone.now()
    version.version += 1
    version.save(update_fields=["baselined_at", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="estimation.version.baselined",
        entity_type="estimate_version",
        entity_public_id=version.public_id,
        after={"version_number": version.version_number, "grand_total": str(version.grand_total)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="estimation.version_baselined",
        aggregate_type="estimate_version",
        aggregate_public_id=version.public_id,
        aggregate_version=version.version,
        payload={"version_number": version.version_number, "grand_total": str(version.grand_total)},
    )
    return baseline
