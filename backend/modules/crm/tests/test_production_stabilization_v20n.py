import uuid

import pytest

from modules.identity.models import Permission

pytestmark = pytest.mark.django_db


def authorize(client, token_pair, company):
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token_pair.access_token}",
        HTTP_X_COMPANY_ID=str(company.public_id),
        HTTP_X_REQUEST_ID=str(uuid.uuid4()),
    )


def test_v20n_permission_catalogue_is_seeded():
    expected = {
        "crm.configuration.read",
        "crm.configuration.manage",
        "crm.automation.read",
        "crm.automation.manage",
        "crm.contact_center.use",
    }
    assert set(
        Permission.objects.filter(code__in=expected).values_list("code", flat=True)
    ) == expected


def test_crm_configuration_no_longer_uses_stage_permission_as_admin_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    legacy_user = user_factory()
    permission_grant_factory(legacy_user, company, ["crm.stage.read"])
    authorize(api_client, token_pair_factory(legacy_user), company)
    denied = api_client.get("/api/v1/crm/configuration")
    assert denied.status_code == 403

    governed_user = user_factory()
    permission_grant_factory(governed_user, company, ["crm.configuration.read"])
    authorize(api_client, token_pair_factory(governed_user), company)
    allowed = api_client.get("/api/v1/crm/configuration")
    assert allowed.status_code == 200


def test_crm_setup_mutation_requires_company_admin_authority(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    crm_editor = user_factory()
    permission_grant_factory(crm_editor, company, ["crm.configuration.manage"])
    authorize(api_client, token_pair_factory(crm_editor), company)
    denied = api_client.post(
        "/api/v1/crm/lead-sources",
        {"code": "field_referral", "name": "Field referral", "channel_type": "referral"},
        format="json",
    )
    assert denied.status_code == 403

    company_admin = user_factory()
    permission_grant_factory(
        company_admin,
        company,
        ["crm.configuration.manage", "access.user.manage"],
    )
    authorize(api_client, token_pair_factory(company_admin), company)
    allowed = api_client.post(
        "/api/v1/crm/lead-sources",
        {"code": "field_referral", "name": "Field referral", "channel_type": "referral"},
        format="json",
    )
    assert allowed.status_code == 201


def test_contact_timeline_requires_explicit_contact_center_permission(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    creator = user_factory()
    permission_grant_factory(
        creator,
        company,
        ["crm.contact.read", "crm.contact.manage", "crm.activity.read"],
    )
    authorize(api_client, token_pair_factory(creator), company)
    created = api_client.post(
        "/api/v1/crm/contacts",
        {"first_name": "Asha", "phone": "+919876543210"},
        format="json",
    )
    assert created.status_code == 201
    contact_id = created.json()["public_id"]

    denied = api_client.get(f"/api/v1/crm/contacts/{contact_id}/timeline")
    assert denied.status_code == 403

    operator = user_factory()
    permission_grant_factory(
        operator,
        company,
        ["crm.contact_center.use", "crm.contact.read", "crm.activity.read"],
    )
    authorize(api_client, token_pair_factory(operator), company)
    allowed = api_client.get(f"/api/v1/crm/contacts/{contact_id}/timeline")
    assert allowed.status_code == 200


def test_protected_contact_reveal_is_reason_limited_minimal_and_no_store(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    permission_grant_factory(
        user,
        company,
        ["crm.contact.read", "crm.contact.manage", "crm.contact.reveal"],
    )
    authorize(api_client, token_pair_factory(user), company)
    created = api_client.post(
        "/api/v1/crm/contacts",
        {
            "first_name": "Secure",
            "email": "secure@example.test",
            "phone": "+919876543210",
        },
        format="json",
    )
    assert created.status_code == 201
    contact_id = created.json()["public_id"]

    invalid = api_client.post(
        f"/api/v1/crm/contacts/{contact_id}/reveal",
        {"reason_code": "customer-support"},
        format="json",
    )
    assert invalid.status_code == 400

    call_reveal = api_client.post(
        f"/api/v1/crm/contacts/{contact_id}/reveal",
        {"reason_code": "crm_call"},
        format="json",
    )
    assert call_reveal.status_code == 200
    assert call_reveal.json() == {"phone": "+919876543210"}
    assert "no-store" in call_reveal["Cache-Control"]
    assert call_reveal["Pragma"] == "no-cache"
