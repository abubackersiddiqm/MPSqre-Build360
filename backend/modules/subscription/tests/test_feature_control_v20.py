import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.subscription.application.feature_control import (
    append_feature_override,
    feature_enabled,
    feature_matrix,
)
from modules.subscription.models import CompanySubscription, PlanVersion

pytestmark = pytest.mark.django_db


def test_specific_feature_override_wins_over_legacy_plan(company_factory):
    company = company_factory()
    plan = PlanVersion.objects.create(
        code="CRM-PRO",
        version=1,
        name="CRM Pro",
        status=PlanVersion.Status.PUBLISHED,
        entitlements={"crm": True},
        limits={},
        effective_from=timezone.now() - timedelta(days=1),
        published_at=timezone.now() - timedelta(days=1),
    )
    CompanySubscription.objects.create(
        company=company,
        plan_version=plan,
        status=CompanySubscription.Status.ACTIVE,
        starts_at=timezone.now() - timedelta(hours=1),
    )

    assert feature_enabled(company=company, code="crm.whatsapp") is True

    append_feature_override(
        company=company,
        code="crm.whatsapp",
        enabled=False,
        reason_code="commercial-control",
        set_by_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )

    assert feature_enabled(company=company, code="crm.whatsapp") is False
    matrix = feature_matrix(company=company)
    row = next(item for item in matrix["items"] if item["code"] == "crm.whatsapp")
    assert row["enabled"] is False
    assert row["source"] == "override"
    assert row["override"]["reason_code"] == "commercial-control"


def test_feature_compatibility_defaults_preserve_existing_tenant_experience(company_factory):
    company = company_factory()

    assert feature_enabled(company=company, code="crm.core") is True
    assert feature_enabled(company=company, code="crm.file_attachments") is True
    assert feature_enabled(company=company, code="tenant.white_label") is True
    assert feature_enabled(company=company, code="tenant.custom_domain") is True
    assert feature_enabled(company=company, code="platform.api_access") is False
