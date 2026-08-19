from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company
from modules.vendor.models import SupplyStage, VendorProfile, VendorQualification


def initial_stage(company: Company, entity_type: str) -> SupplyStage:
    stage = (
        SupplyStage.objects.filter(
            company=company,
            entity_type=entity_type,
            is_initial=True,
            is_active=True,
            effective_from__lte=timezone.now(),
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        .order_by("sort_order")
        .first()
    )
    if stage is None:
        raise ValidationError(f"No initial {entity_type} stage is configured")
    return stage


def resolve_stage(
    company: Company,
    public_id: uuid.UUID,
    entity_type: str,
) -> SupplyStage:
    stage = (
        SupplyStage.objects.filter(
            company=company,
            public_id=public_id,
            entity_type=entity_type,
            is_active=True,
            effective_from__lte=timezone.now(),
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        .first()
    )
    if stage is None:
        raise ValidationError("Supply stage was not found")
    return stage


def available_transitions(stage: SupplyStage) -> QuerySet[SupplyStage]:
    return (
        SupplyStage.objects.filter(
            company=stage.company,
            entity_type=stage.entity_type,
            code__in=stage.allowed_next_codes,
            is_active=True,
            effective_from__lte=timezone.now(),
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=timezone.now()))
        .order_by("sort_order")
    )


def _record(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
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
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type=entity_type,
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


@transaction.atomic
def create_vendor(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    legal_name: str,
    display_name: str,
    categories: list[str] | None = None,
    service_regions: list[str] | None = None,
    tax_reference_masked: str = "",
    primary_contact_name: str = "",
    primary_contact_email: str = "",
    primary_contact_phone: str = "",
) -> VendorProfile:
    vendor = VendorProfile(
        company=company,
        code=code.strip().upper(),
        legal_name=legal_name.strip(),
        display_name=display_name.strip(),
        stage=initial_stage(company, SupplyStage.EntityType.VENDOR),
        categories=categories or [],
        service_regions=service_regions or [],
        tax_reference_masked=tax_reference_masked.strip(),
        primary_contact_name=primary_contact_name.strip(),
        primary_contact_email=primary_contact_email.strip().lower(),
        primary_contact_phone=primary_contact_phone.strip(),
    )
    vendor.full_clean()
    vendor.save()
    _record(
        actor=actor,
        company=company,
        action="vendor.created",
        entity_type="vendor",
        entity_public_id=vendor.public_id,
        version=vendor.version,
        payload={
            "code": vendor.code,
            "stage": vendor.stage.code,
            "version": vendor.version,
        },
    )
    return vendor


@transaction.atomic
def transition_vendor(
    *,
    company: Company,
    actor: RequestActor,
    vendor_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> VendorProfile:
    vendor = (
        VendorProfile.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=vendor_public_id)
        .first()
    )
    if vendor is None:
        raise ValidationError("Vendor was not found")
    if vendor.version != expected_version:
        raise ValidationError("Vendor changed; refresh before retrying")

    target = resolve_stage(
        company,
        target_stage_public_id,
        SupplyStage.EntityType.VENDOR,
    )
    if target.code not in vendor.stage.allowed_next_codes:
        raise ValidationError("Requested vendor transition is not permitted")

    previous_stage = vendor.stage.code
    vendor.stage = target
    vendor.version += 1
    if target.code == "suspended":
        vendor.suspended_at = timezone.now()
    elif target.code == "retired":
        vendor.retired_at = timezone.now()
    elif target.code == "qualified":
        vendor.suspended_at = None
    vendor.full_clean()
    vendor.save()
    _record(
        actor=actor,
        company=company,
        action="vendor.transitioned",
        entity_type="vendor",
        entity_public_id=vendor.public_id,
        version=vendor.version,
        payload={
            "from": previous_stage,
            "to": target.code,
            "reason_code": reason_code.strip(),
            "version": vendor.version,
        },
    )
    return vendor


@transaction.atomic
def qualify_vendor(
    *,
    company: Company,
    actor: RequestActor,
    vendor_public_id: uuid.UUID,
    score: Decimal,
    decision: str,
    expected_version: int,
    notes: str = "",
    expires_at: Any = None,
) -> VendorProfile:
    vendor = (
        VendorProfile.objects.select_for_update()
        .select_related("stage")
        .filter(company=company, public_id=vendor_public_id)
        .first()
    )
    if vendor is None:
        raise ValidationError("Vendor was not found")
    if vendor.version != expected_version:
        raise ValidationError("Vendor changed; refresh before retrying")
    if vendor.stage.code not in {"registered", "under_review", "rejected"}:
        raise ValidationError("Vendor is not in a qualification-eligible stage")
    if decision not in VendorQualification.Decision.values:
        raise ValidationError("Qualification decision is invalid")

    qualification = VendorQualification(
        company=company,
        vendor=vendor,
        score=score,
        decision=decision,
        notes=notes.strip(),
        decided_by_public_id=actor.user_public_id,
        decided_at=timezone.now(),
        expires_at=expires_at,
    )
    qualification.full_clean()
    qualification.save()

    target_code = (
        "qualified"
        if decision == VendorQualification.Decision.APPROVED
        else "rejected"
    )
    target = SupplyStage.objects.filter(
        company=company,
        entity_type=SupplyStage.EntityType.VENDOR,
        code=target_code,
        is_active=True,
    ).first()
    if target is None:
        raise ValidationError("Vendor lifecycle is not initialized")

    vendor.stage = target
    vendor.version += 1
    vendor.qualified_at = (
        timezone.now()
        if decision == VendorQualification.Decision.APPROVED
        else None
    )
    vendor.full_clean()
    vendor.save()
    _record(
        actor=actor,
        company=company,
        action="vendor.qualification_decided",
        entity_type="vendor",
        entity_public_id=vendor.public_id,
        version=vendor.version,
        payload={
            "decision": decision,
            "score": str(score),
            "stage": target.code,
            "version": vendor.version,
        },
    )
    return vendor
