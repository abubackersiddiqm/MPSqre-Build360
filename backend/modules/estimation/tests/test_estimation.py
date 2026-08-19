import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.estimation.application.services import (
    baseline_estimate_version,
    create_boq_item,
    create_estimate,
)
from modules.platform.actors import RequestActor
from modules.projects.application.services import create_project
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


def stage(company, entity_type, code, outcome, *, initial=False, baseline=False):
    return DeliveryStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=code.title(),
        outcome=outcome,
        sort_order=10,
        allowed_next_codes=[],
        is_initial=initial,
        allows_baseline=baseline,
        effective_from=timezone.now() - timedelta(minutes=1),
    )


def setup_estimate(company, user, membership):
    stage(
        company,
        DeliveryStage.EntityType.PROJECT,
        "planning",
        DeliveryStage.Outcome.OPEN,
        initial=True,
    )
    stage(
        company,
        DeliveryStage.EntityType.ESTIMATE_VERSION,
        "approved",
        DeliveryStage.Outcome.APPROVED,
        initial=True,
        baseline=True,
    )
    project = create_project(
        company=company,
        actor=actor(user, membership),
        code="P-EST",
        name="Estimate project",
    )
    return create_estimate(
        company=company,
        actor=actor(user, membership),
        project_public_id=project.public_id,
        code="EST-001",
        name="Tender estimate",
    )


def test_boq_totals_and_baseline_are_fixed_and_idempotent(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    estimate, version = setup_estimate(company, user, membership)
    create_boq_item(
        company=company,
        actor=actor(user, membership),
        version_public_id=version.public_id,
        item_code="CONC-001",
        description="Concrete",
        unit_code="M3",
        quantity=Decimal("10"),
        rate=Decimal("125.50"),
        tax_rate_percent=Decimal("18"),
    )
    version.refresh_from_db()
    assert version.subtotal == Decimal("1255.0000")
    assert version.tax_total == Decimal("225.9000")
    assert version.grand_total == Decimal("1480.9000")

    first = baseline_estimate_version(
        company=company,
        actor=actor(user, membership),
        version_public_id=version.public_id,
        expected_version=version.version,
    )
    second = baseline_estimate_version(
        company=company,
        actor=actor(user, membership),
        version_public_id=version.public_id,
        expected_version=version.version + 1,
    )
    assert first.public_id == second.public_id
    assert first.snapshot["version"]["grand_total"] == "1480.9000"


def test_boq_tax_rate_cannot_exceed_one_hundred(
    company_factory,
    user_factory,
    membership_factory,
):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    _, version = setup_estimate(company, user, membership)

    with pytest.raises(ValidationError):
        create_boq_item(
            company=company,
            actor=actor(user, membership),
            version_public_id=version.public_id,
            item_code="INVALID-TAX",
            description="Invalid tax",
            unit_code="EA",
            quantity=Decimal("1"),
            rate=Decimal("100"),
            tax_rate_percent=Decimal("101"),
        )
