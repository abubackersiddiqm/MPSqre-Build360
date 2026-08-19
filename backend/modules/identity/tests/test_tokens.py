import uuid
from collections.abc import Callable

import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from modules.identity.application.tokens import (
    TokenPair,
    authenticate_access_token,
    has_recent_assurance,
    rotate_refresh_token,
)
from modules.identity.models import AuthSession, RefreshToken, User


@pytest.mark.django_db
def test_refresh_rotation_is_single_use(
    user_factory: Callable[..., User],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    first = token_pair_factory(user)
    second = rotate_refresh_token(
        encoded_token=first.refresh_token,
        correlation_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert second.refresh_token != first.refresh_token
    assert RefreshToken.objects.filter(used_at__isnull=False).count() == 1
    assert RefreshToken.objects.filter(used_at__isnull=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_refresh_reuse_revokes_complete_session(
    user_factory: Callable[..., User],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    first = token_pair_factory(user)
    rotate_refresh_token(
        encoded_token=first.refresh_token,
        correlation_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    with pytest.raises(AuthenticationFailed, match="Session revoked"):
        rotate_refresh_token(
            encoded_token=first.refresh_token,
            correlation_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    session = AuthSession.objects.get(public_id=first.session_public_id)
    assert session.revoked_at is not None
    assert not RefreshToken.objects.filter(session=session, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_revoked_session_invalidates_unexpired_access_token(
    api_client: APIClient,
    user_factory: Callable[..., User],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    pair = token_pair_factory(user)
    principal = authenticate_access_token(pair.access_token)
    principal.session.revoked_at = principal.session.created_at
    principal.session.revoke_reason = "test"
    principal.session.save(update_fields=["revoked_at", "revoke_reason"])

    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_password_login_uses_argon2(
    api_client: APIClient,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="login@example.test")
    assert user.password.startswith("argon2$")

    response = api_client.post(
        "/api/v1/auth/token",
        {
            "email": "LOGIN@example.test",
            "password": "A-secure-test-password-42!",
            "device_id": str(uuid.uuid4()),
            "device_name": "Test browser",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["access_token"]
    assert response.data["refresh_token"]


@pytest.mark.django_db
def test_password_login_establishes_recent_assurance(
    user_factory: Callable[..., User],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    principal = authenticate_access_token(token_pair_factory(user_factory()).access_token)
    assert has_recent_assurance(principal)
