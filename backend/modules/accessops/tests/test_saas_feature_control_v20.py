import uuid

import pytest

from modules.accessops.models import PlatformOperator
from modules.subscription.application.feature_control import feature_enabled

pytestmark = pytest.mark.django_db


def authorize_platform(client, token_pair):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def test_root_operator_can_control_company_feature_matrix(
    api_client,
    company_factory,
    user_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory(email="root-feature-control@example.test")
    PlatformOperator.objects.create(user=user, operator_type_code="ROOT_OPERATOR")
    authorize_platform(api_client, token_pair_factory(user))

    before = api_client.get(
        f"/api/v1/access-control/platform/companies/{company.public_id}/feature-matrix"
    )
    assert before.status_code == 200
    assert any(item["code"] == "crm.core" for item in before.json()["items"])

    changed = api_client.patch(
        f"/api/v1/access-control/platform/companies/{company.public_id}/feature-matrix",
        {
            "feature_code": "crm.core",
            "enabled": False,
            "reason_code": "uat-disable",
        },
        format="json",
    )
    assert changed.status_code == 200
    assert feature_enabled(company=company, code="crm.core") is False
    row = next(item for item in changed.json()["items"] if item["code"] == "crm.core")
    assert row["enabled"] is False
    assert row["source"] == "override"


def test_non_root_operator_cannot_change_feature_matrix(
    api_client,
    company_factory,
    user_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory(email="support-feature-control@example.test")
    PlatformOperator.objects.create(user=user, operator_type_code="SUPPORT_OPERATOR")
    authorize_platform(api_client, token_pair_factory(user))

    response = api_client.patch(
        f"/api/v1/access-control/platform/companies/{company.public_id}/feature-matrix",
        {
            "feature_code": "crm.core",
            "enabled": False,
            "reason_code": "should-not-work",
        },
        format="json",
    )
    assert response.status_code == 403
