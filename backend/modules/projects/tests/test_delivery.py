import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.platform.actors import RequestActor
from modules.projects.application.services import (
    baseline_project,
    create_project,
    create_task,
    transition_task,
)
from modules.projects.models import DeliveryStage

pytestmark = pytest.mark.django_db


def actor(user, membership) -> RequestActor:
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


def stage(company, *, entity_type, code, outcome, next_codes=None, initial=False, baseline=False):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=code.replace("_", " ").title(),
        outcome=outcome,
        sort_order=10,
        allowed_next_codes=next_codes or [],
        is_initial=initial,
        allows_baseline=baseline,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def test_project_baseline_serializes_dates(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    stage(
        company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="planning",
        outcome=DeliveryStage.Outcome.OPEN,
        initial=True,
        baseline=True,
    )
    stage(
        company,
        entity_type=DeliveryStage.EntityType.TASK,
        code="not_started",
        outcome=DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    project = create_project(
        company=company,
        actor=actor(user, membership),
        code="P-001",
        name="Tower project",
        planned_start_date=date(2026, 8, 1),
        planned_end_date=date(2027, 7, 31),
        approved_budget=Decimal("1250000"),
    )
    create_task(
        company=company,
        actor=actor(user, membership),
        project_public_id=project.public_id,
        code="T-001",
        title="Mobilisation",
        planned_start_date=date(2026, 8, 1),
        planned_end_date=date(2026, 8, 7),
    )

    baseline = baseline_project(
        company=company,
        actor=actor(user, membership),
        project_public_id=project.public_id,
        expected_version=1,
    )

    assert baseline.snapshot["project"]["planned_start_date"] == "2026-08-01"
    assert baseline.snapshot["tasks"][0]["planned_end_date"] == "2026-08-07"


def test_task_transition_preserves_explicit_zero_progress(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    stage(
        company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="planning",
        outcome=DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    initial = stage(
        company,
        entity_type=DeliveryStage.EntityType.TASK,
        code="not_started",
        outcome=DeliveryStage.Outcome.OPEN,
        next_codes=["in_progress"],
        initial=True,
    )
    target = stage(
        company,
        entity_type=DeliveryStage.EntityType.TASK,
        code="in_progress",
        outcome=DeliveryStage.Outcome.OPEN,
    )
    project = create_project(
        company=company,
        actor=actor(user, membership),
        code="P-002",
        name="Fit-out",
    )
    task = create_task(
        company=company,
        actor=actor(user, membership),
        project_public_id=project.public_id,
        code="T-002",
        title="Layout marking",
    )
    task.progress_percent = 30
    task.save(update_fields=["progress_percent"])
    initial.allowed_next_codes = [target.code]
    initial.save(update_fields=["allowed_next_codes"])

    changed = transition_task(
        company=company,
        actor=actor(user, membership),
        task_public_id=task.public_id,
        target_stage_public_id=target.public_id,
        expected_version=1,
        progress_percent=0,
    )

    assert changed.progress_percent == 0
    with pytest.raises(ValidationError, match="refresh before retrying"):
        transition_task(
            company=company,
            actor=actor(user, membership),
            task_public_id=task.public_id,
            target_stage_public_id=target.public_id,
            expected_version=1,
        )
