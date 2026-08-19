import uuid

import pytest
from django.utils import timezone

from modules.subscription.models import EntitlementOverride

pytestmark = pytest.mark.django_db


def authorize(client, token_pair, company):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company.public_id),
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def test_api_client_endpoints_require_platform_api_access_entitlement(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    permission_grant_factory(user, company, ["integration.api_client.read"])
    token_pair = token_pair_factory(user)
    authorize(api_client, token_pair, company)

    denied = api_client.get("/api/v1/integrations/api-clients")
    assert denied.status_code == 403

    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="platform.api_access",
        enabled=True,
        effective_from=timezone.now(),
        reason_code="v20-api-access-test",
        set_by_public_id=user.public_id,
    )

    allowed = api_client.get("/api/v1/integrations/api-clients")
    assert allowed.status_code == 200
    assert allowed.json() == {"items": []}
