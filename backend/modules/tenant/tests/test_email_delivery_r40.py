from __future__ import annotations

import pytest
from django.core import mail
from modules.tenant.application.email_delivery import (
    encrypt_smtp_password,
    resolve_password_reset_scope,
    send_transactional_email,
)
from modules.tenant.models import CompanyEmailDeliveryProfile, TenantDomain

pytestmark = pytest.mark.django_db


def test_company_smtp_password_is_ciphertext(company_factory):
    company = company_factory()
    encrypted = encrypt_smtp_password("secret-password")
    assert encrypted
    assert encrypted != "secret-password"
    profile = CompanyEmailDeliveryProfile.objects.create(
        company=company,
        delivery_mode="TENANT_SMTP",
        smtp_host="smtp.example.test",
        smtp_port=587,
        smtp_username="mailer@example.test",
        smtp_password_encrypted=encrypted,
        from_email="mailer@example.test",
        status="PENDING",
    )
    assert profile.smtp_password_encrypted != "secret-password"


def test_platform_route_is_default_without_active_tenant_smtp(
    company_factory,
    settings,
    monkeypatch,
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr(
        "modules.tenant.application.email_delivery.feature_enabled",
        lambda *, company, code: False,
    )
    company = company_factory()
    result = send_transactional_email(
        company=company,
        subject="Test",
        text="test",
        html="<p>test</p>",
        to=["recipient@example.test"],
    )
    assert result.route == "PLATFORM"
    assert result.status == "LOCAL_PREVIEW"
    assert len(mail.outbox) == 1


def test_tenant_host_password_reset_requires_membership(
    company_factory,
    user_factory,
):
    company = company_factory()
    user = user_factory(email="outsider@example.test")
    TenantDomain.objects.create(
        company=company,
        domain="portal.example.test",
        domain_type=TenantDomain.DomainType.CUSTOM_DOMAIN,
        status=TenantDomain.Status.ACTIVE,
        ssl_status=TenantDomain.SslStatus.ACTIVE,
    )
    scope = resolve_password_reset_scope(user=user, public_host="portal.example.test")
    assert scope.allowed is False
    assert scope.company is None


def test_single_membership_scope_can_select_white_label_company(
    company_factory,
    user_factory,
    membership_factory,
    monkeypatch,
):
    company = company_factory()
    user = user_factory(email="member@example.test")
    membership_factory(user, company)
    monkeypatch.setattr(
        "modules.tenant.application.email_delivery.feature_enabled",
        lambda *, company, code: code == "tenant.white_label",
    )
    scope = resolve_password_reset_scope(user=user, public_host="app.build360.example")
    assert scope.allowed is True
    assert scope.company == company
    assert scope.source == "SINGLE_TENANT_MEMBERSHIP"
