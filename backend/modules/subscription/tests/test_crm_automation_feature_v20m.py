import uuid

import pytest

from modules.subscription.application.feature_control import (
    apply_feature_preset,
    feature_enabled,
)

pytestmark = pytest.mark.django_db


def test_crm_automation_is_governed_add_on_and_package_can_enable_it(company_factory):
    company = company_factory()
    assert feature_enabled(company=company, code="crm.automation") is False

    apply_feature_preset(
        company=company,
        preset_code="CRM_ONLY",
        reason_code="automation-package-test",
        set_by_public_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
    )

    assert feature_enabled(company=company, code="crm.automation") is True
