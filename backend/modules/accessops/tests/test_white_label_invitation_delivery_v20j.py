import uuid

import pytest
from django.core import mail
from django.test import override_settings

from modules.accessops.application.invitation_delivery import deliver_invitation_email
from modules.accessops.application.services import create_company_with_admin_invitation
from modules.identity.models import Role, RolePermission
from modules.tenant.models import CompanyBrandProfile, TenantDomain

pytestmark = pytest.mark.django_db


def create_company(operator_user, *, code: str, preset_code: str):
    return create_company_with_admin_invitation(
        code=code,
        legal_name=f"{code} Private Limited",
        display_name="Parry's Power Tools" if code == "PPTV20J" else "CRM Tenant",
        locale="en-IN",
        timezone_name="Asia/Kolkata",
        currency="INR",
        unit_system_code="METRIC",
        fiscal_year_start_month=4,
        plan_code=preset_code,
        admin_email=f"admin-{code.lower()}@example.test",
        admin_display_name="Primary Admin",
        admin_employee_number=f"ADM-{code}",
        actor_public_id=operator_user.public_id,
        correlation_id=uuid.uuid4(),
        preset_code=preset_code,
    )


def test_company_admin_gets_brand_governance_but_company_user_does_not(user_factory):
    operator = user_factory(email="v20j-admin-scope@example.test")
    company, _, _ = create_company(operator, code="PPTV20J", preset_code="FULL_BUILD360")

    admin = Role.objects.get(company_public_id=company.public_id, code="COMPANY_ADMIN", retired_at__isnull=True)
    admin_codes = set(RolePermission.objects.filter(role=admin).values_list("permission__code", flat=True))
    assert {
        "access.view",
        "access.user.manage",
        "tenant.branding.read",
        "tenant.branding.manage",
        "tenant.domain.read",
        "tenant.domain.manage",
    }.issubset(admin_codes)
    assert "crm.dashboard.read" not in admin_codes

    company_user = Role.objects.get(company_public_id=company.public_id, code="COMPANY_USER", retired_at__isnull=True)
    user_codes = set(RolePermission.objects.filter(role=company_user).values_list("permission__code", flat=True))
    assert "tenant.branding.manage" not in user_codes
    assert "tenant.domain.manage" not in user_codes


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    BUILD360_TRANSACTIONAL_FROM_EMAIL="notifications@mpsqre.com",
    BUILD360_PUBLIC_WEB_URL="http://localhost:3000",
)
def test_white_label_employee_activation_email_uses_tenant_brand_and_verified_active_domain(user_factory):
    operator = user_factory(email="v20j-mail-brand@example.test")
    company, invitation, token = create_company(operator, code="PPTV20J", preset_code="FULL_BUILD360")
    CompanyBrandProfile.objects.update_or_create(
        company=company,
        defaults={
            "product_name": "Parry's Power Tools",
            "sender_name": "Parry's Power Tools",
            "support_email": "support@parrys.example",
            "primary_color": "#174D3C",
            "accent_color": "#0F766E",
            "powered_by_build360": False,
        },
    )
    TenantDomain.objects.create(
        company=company,
        domain="portal.parrys.example",
        domain_type=TenantDomain.DomainType.CUSTOM_DOMAIN,
        status=TenantDomain.Status.ACTIVE,
        ssl_status=TenantDomain.SslStatus.ACTIVE,
        is_primary=True,
    )

    result = deliver_invitation_email(invitation=invitation, raw_token=token)

    assert result["status"] == "LOCAL_PREVIEW"
    assert result["brand_name"] == "Parry's Power Tools"
    assert result["acceptance_url"].startswith("https://portal.parrys.example/accept-invitation?token=")
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.subject == "You're invited to Parry's Power Tools"
    assert sent.from_email == "Parry's Power Tools <notifications@mpsqre.com>"
    assert sent.reply_to == ["support@parrys.example"]
    assert "Powered by MPSqre Build360" not in sent.body


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    BUILD360_TRANSACTIONAL_FROM_EMAIL="notifications@mpsqre.com",
    BUILD360_PUBLIC_WEB_URL="http://localhost:3000",
)
def test_non_white_label_invitation_falls_back_to_build360_brand(user_factory):
    operator = user_factory(email="v20j-mail-fallback@example.test")
    company, invitation, token = create_company(operator, code="CRMV20J", preset_code="CRM_ONLY")

    result = deliver_invitation_email(invitation=invitation, raw_token=token)

    assert result["brand_name"] == "MPSqre Build360"
    assert result["acceptance_url"].startswith("http://localhost:3000/accept-invitation?token=")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].from_email == "MPSqre Build360 <notifications@mpsqre.com>"
