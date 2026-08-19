from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.fieldops.models import FieldStage
from modules.tenant.models import Company


def active_stages(company: Company, entity_type: str) -> QuerySet[FieldStage]:
    now = timezone.now()
    return FieldStage.objects.filter(
        company=company,
        entity_type=entity_type,
        is_active=True,
        effective_from__lte=now,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))


def initial_stage(company: Company, entity_type: str) -> FieldStage:
    stage = active_stages(company, entity_type).filter(is_initial=True).first()
    if stage is None:
        raise ValidationError(f"No initial field stage is configured for {entity_type}")
    return stage


def resolve_stage(company: Company, entity_type: str, code: str) -> FieldStage:
    stage = active_stages(company, entity_type).filter(code=code.strip().lower()).first()
    if stage is None:
        raise ValidationError("The requested field stage is not available")
    return stage


def available_transitions(stage: FieldStage) -> QuerySet[FieldStage]:
    return active_stages(stage.company, stage.entity_type).filter(
        code__in=stage.allowed_next_codes
    )


def assert_transition(current: FieldStage, target: FieldStage) -> None:
    if current.company_id != target.company_id or current.entity_type != target.entity_type:
        raise ValidationError("Field stage transition cannot cross scope")
    if target.code not in current.allowed_next_codes:
        raise ValidationError(f"Transition from {current.code} to {target.code} is not allowed")
