from __future__ import annotations

import pytest

from modules.integration.models import ConnectorProfile, IntegrationProviderCatalog

pytestmark = pytest.mark.django_db


def test_provider_catalog_reports_company_connection_status(api_client, company_factory, user_factory, permission_grant_factory, token_pair_factory):
    company = company_factory()
    user = user_factory()
    permission_grant_factory(user, company, ["integration.dashboard.read"])
    pair = token_pair_factory(user)
    provider, _ = IntegrationProviderCatalog.objects.get_or_create(
        code="TEST_PROVIDER",
        defaults={
            "name": "Test Provider",
            "category": IntegrationProviderCatalog.Category.AUTOMATION,
            "connector_type": ConnectorProfile.ConnectorType.CUSTOM,
            "provider_code": "TEST_PROVIDER",
            "description": "Test provider",
            "capabilities": ["api"],
            "configuration_schema": {},
        },
    )
    ConnectorProfile.objects.create(
        company=company,
        code="TEST-01",
        name="Test connection",
        connector_type=ConnectorProfile.ConnectorType.CUSTOM,
        provider_code=provider.provider_code,
        direction=ConnectorProfile.Direction.BIDIRECTIONAL,
        status=ConnectorProfile.Status.ACTIVE,
        public_config={},
        allowed_data_classes=[],
    )
    response = api_client.get(
        "/api/v1/integrations/provider-catalog",
        headers={"Authorization": f"Bearer {pair.access_token}", "X-Company-Id": str(company.public_id)},
    )
    assert response.status_code == 200
    item = next(value for value in response.data["items"] if value["code"] == "TEST_PROVIDER")
    assert item["connection"]["status"] == "ACTIVE"
    assert "secret_ref" not in item
