from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.equipment.application.services import create_equipment, record_meter
from modules.fieldops.application.stages import assert_transition
from modules.fieldops.application.sync import receive_operation
from modules.fieldops.models import FieldStage, OfflineOperation
from modules.labour.application.services import create_worker, record_attendance
from modules.platform.actors import RequestActor
from modules.projects.models import DeliveryStage, Project


@pytest.fixture
def actor(user_factory, membership_factory, company_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    return (
        company,
        membership,
        RequestActor(
            user_public_id=user.public_id,
            membership_public_id=membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
    )


def field_stage(company, entity_type: str, code: str, *, initial: bool = False, next_codes=None):
    return FieldStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=code.replace("_", " ").title(),
        outcome="open",
        allowed_next_codes=next_codes or [],
        is_initial=initial,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def project_for(company, membership):
    stage = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="active",
        name="Active",
        outcome=DeliveryStage.Outcome.OPEN,
        is_initial=True,
        effective_from=timezone.now() - timedelta(minutes=1),
    )
    return Project.objects.create(
        company=company,
        code=f"P-{uuid.uuid4().hex[:6]}",
        name="Field test project",
        stage=stage,
        manager_membership_public_id=membership.public_id,
        currency=company.currency,
    )


@pytest.mark.django_db
def test_field_stage_rejects_unconfigured_transition(actor):
    company, _, _ = actor
    start = field_stage(company, FieldStage.EntityType.ATTENDANCE, "draft", next_codes=["submitted"])
    target = field_stage(company, FieldStage.EntityType.ATTENDANCE, "approved")
    with pytest.raises(ValidationError):
        assert_transition(start, target)


@pytest.mark.django_db
def test_attendance_operation_is_idempotent(actor):
    company, membership, request_actor = actor
    field_stage(company, FieldStage.EntityType.ATTENDANCE, "draft", initial=True)
    project = project_for(company, membership)
    worker = create_worker(
        company=company,
        actor=request_actor,
        code="W-001",
        display_name="Worker One",
        worker_type="contract",
        trade_code="masonry",
        joined_on=timezone.localdate(),
        currency=company.currency,
    )
    operation_id = uuid.uuid4()
    first = record_attendance(
        company=company,
        actor=request_actor,
        worker_public_id=worker.public_id,
        project_public_id=project.public_id,
        work_date=timezone.localdate(),
        regular_hours=Decimal("8"),
        operation_id=operation_id,
    )
    second = record_attendance(
        company=company,
        actor=request_actor,
        worker_public_id=worker.public_id,
        project_public_id=project.public_id,
        work_date=timezone.localdate(),
        regular_hours=Decimal("8"),
        operation_id=operation_id,
    )
    assert first.pk == second.pk


@pytest.mark.django_db
def test_meter_cannot_move_backwards(actor):
    company, _, request_actor = actor
    field_stage(company, FieldStage.EntityType.EQUIPMENT, "available", initial=True)
    asset = create_equipment(
        company=company,
        actor=request_actor,
        code="EQ-001",
        name="Excavator",
        category_code="earthmoving",
        currency=company.currency,
    )
    record_meter(
        company=company,
        actor=request_actor,
        equipment_public_id=asset.public_id,
        reading=Decimal("100"),
        reading_at=timezone.now(),
    )
    with pytest.raises(ValidationError):
        record_meter(
            company=company,
            actor=request_actor,
            equipment_public_id=asset.public_id,
            reading=Decimal("99"),
            reading_at=timezone.now(),
        )


@pytest.mark.django_db
def test_offline_operation_rejects_unapproved_type(actor):
    company, membership, request_actor = actor
    with pytest.raises(ValidationError):
        receive_operation(
            company=company,
            actor=request_actor,
            membership_public_id=membership.public_id,
            operation_id=uuid.uuid4(),
            device_id=uuid.uuid4(),
            operation_type="finance.payment.post",
            aggregate_type="payment",
            payload={},
        )
    assert OfflineOperation.objects.filter(company=company).count() == 0
