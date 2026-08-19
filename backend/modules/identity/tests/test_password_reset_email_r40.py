from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_password_reset_request_sends_generic_platform_email(user_factory, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.BUILD360_PUBLIC_WEB_URL = "https://app.build360.test"
    user = user_factory(email="reset-r40@example.test")
    client = APIClient()
    response = client.post(
        "/api/v1/auth/password-reset/request",
        {"email": user.email},
        format="json",
        HTTP_X_BUILD360_PUBLIC_HOST="app.build360.test",
    )
    assert response.status_code == 202
    assert "exists" in response.data["message"]
    assert len(mail.outbox) == 1
    assert "reset-password?" in mail.outbox[0].body


def test_unknown_password_reset_account_never_sends_mail(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client = APIClient()
    response = client.post(
        "/api/v1/auth/password-reset/request",
        {"email": "missing-r40@example.test"},
        format="json",
        HTTP_X_BUILD360_PUBLIC_HOST="app.build360.test",
    )
    assert response.status_code == 202
    assert len(mail.outbox) == 0
