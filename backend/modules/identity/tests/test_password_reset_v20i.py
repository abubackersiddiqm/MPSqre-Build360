
import pytest
from rest_framework.exceptions import AuthenticationFailed

from modules.identity.application.tokens import authenticate_access_token
from modules.identity.models import AuthSession

pytestmark = pytest.mark.django_db


def test_password_reset_request_is_generic_and_local_debug_link_is_one_time(
    api_client,
    settings,
    user_factory,
    token_pair_factory,
):
    settings.BUILD360_ENVIRONMENT = "demo"
    user = user_factory(email="reset-v20i@example.test")
    pair = token_pair_factory(user)

    response = api_client.post(
        "/api/v1/auth/password-reset/request",
        {"email": "RESET-V20I@example.test"},
        format="json",
    )
    assert response.status_code == 202
    assert "active Build360 account" in response.data["message"]
    uid = response.data["debug_uid"]
    token = response.data["debug_token"]

    confirm = api_client.post(
        "/api/v1/auth/password-reset/confirm",
        {"uid": uid, "token": token, "password": "New-secure-password-84!"},
        format="json",
    )
    assert confirm.status_code == 200
    user.refresh_from_db()
    assert user.check_password("New-secure-password-84!")
    session = AuthSession.objects.get(public_id=pair.session_public_id)
    assert session.revoked_at is not None
    with pytest.raises(AuthenticationFailed):
        authenticate_access_token(pair.access_token)

    reused = api_client.post(
        "/api/v1/auth/password-reset/confirm",
        {"uid": uid, "token": token, "password": "Another-secure-password-85!"},
        format="json",
    )
    assert reused.status_code == 400


def test_password_reset_request_does_not_disclose_unknown_email(api_client, settings):
    settings.BUILD360_ENVIRONMENT = "demo"
    response = api_client.post(
        "/api/v1/auth/password-reset/request",
        {"email": "does-not-exist@example.test"},
        format="json",
    )
    assert response.status_code == 202
    assert "debug_uid" not in response.data
    assert "debug_token" not in response.data
    assert "active Build360 account" in response.data["message"]


def test_new_password_reset_request_invalidates_previous_link(api_client, settings, user_factory):
    settings.BUILD360_ENVIRONMENT = "demo"
    user_factory(email="latest-reset-v20i@example.test")
    first = api_client.post(
        "/api/v1/auth/password-reset/request",
        {"email": "latest-reset-v20i@example.test"},
        format="json",
    )
    second = api_client.post(
        "/api/v1/auth/password-reset/request",
        {"email": "latest-reset-v20i@example.test"},
        format="json",
    )
    stale = api_client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "uid": first.data["debug_uid"],
            "token": first.data["debug_token"],
            "password": "Stale-secure-password-86!",
        },
        format="json",
    )
    assert stale.status_code == 400
    fresh = api_client.post(
        "/api/v1/auth/password-reset/confirm",
        {
            "uid": second.data["debug_uid"],
            "token": second.data["debug_token"],
            "password": "Fresh-secure-password-87!",
        },
        format="json",
    )
    assert fresh.status_code == 200
