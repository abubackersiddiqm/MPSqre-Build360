import uuid

import pytest

from modules.accessops.application.services import (
    accept_invitation,
    create_company_with_admin_invitation,
)
from modules.accessops.models import AccessInvitation, PlatformOperator

pytestmark = pytest.mark.django_db


def authorize_platform(client, pair):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {pair.access_token}",
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def create_company(operator_user):
    return create_company_with_admin_invitation(
        code="RECOV20I",
        legal_name="Recovery V20I Private Limited",
        display_name="Recovery V20I",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code="CRM_ONLY",
        admin_email="primary-admin-v20i@example.test",
        admin_display_name="Primary Admin",
        admin_employee_number="ADM-V20I",
        actor_public_id=operator_user.public_id,
        correlation_id=uuid.uuid4(),
        preset_code="CRM_ONLY",
    )


def test_root_operator_can_regenerate_unactivated_primary_admin_link(
    api_client,
    user_factory,
    token_pair_factory,
):
    operator_user = user_factory(email="root-recovery-v20i@example.test")
    PlatformOperator.objects.create(user=operator_user, operator_type_code="ROOT_OPERATOR")
    company, original, _ = create_company(operator_user)
    authorize_platform(api_client, token_pair_factory(operator_user))

    response = api_client.post(
        f"/api/v1/access-control/platform/companies/{company.public_id}/primary-admin-invitation",
        {"ttl_hours": 72},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["email"] == "primary-admin-v20i@example.test"
    assert response.data["acceptance_token"]
    original.refresh_from_db()
    assert original.revoked_at is not None
    newest = AccessInvitation.objects.get(public_id=response.data["public_id"])
    assert newest.revoked_at is None
    assert newest.accepted_at is None


def test_active_primary_admin_uses_password_reset_not_activation_reissue(
    api_client,
    user_factory,
    token_pair_factory,
):
    operator_user = user_factory(email="root-active-v20i@example.test")
    PlatformOperator.objects.create(user=operator_user, operator_type_code="ROOT_OPERATOR")
    company, _, raw_token = create_company(operator_user)
    accept_invitation(
        raw_token=raw_token,
        password="Company-admin-password-42!",
        correlation_id=uuid.uuid4(),
    )
    authorize_platform(api_client, token_pair_factory(operator_user))

    response = api_client.post(
        f"/api/v1/access-control/platform/companies/{company.public_id}/primary-admin-invitation",
        {"ttl_hours": 72},
        format="json",
    )
    assert response.status_code == 400
    assert "Forgot password" in str(response.data)
