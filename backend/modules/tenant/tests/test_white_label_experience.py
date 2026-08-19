from __future__ import annotations

import pytest
from django.utils import timezone

from modules.tenant.models import CompanyBrandProfile, TenantDomain

pytestmark = pytest.mark.django_db


def auth_headers(pair, company):
    return {"Authorization": f"Bearer {pair.access_token}", "X-Company-Id": str(company.public_id)}


def test_branding_is_tenant_scoped_and_versioned(api_client, company_factory, user_factory, permission_grant_factory, token_pair_factory):
    company = company_factory(display_name="Alpha Builders")
    user = user_factory()
    permission_grant_factory(user, company, ["tenant.branding.read", "tenant.branding.manage"])
    pair = token_pair_factory(user)
    CompanyBrandProfile.objects.get_or_create(company=company, defaults={"product_name": company.display_name})

    response = api_client.get("/api/v1/companies/current/branding", headers=auth_headers(pair, company))
    assert response.status_code == 200
    version = response.data["version"]

    changed = api_client.patch(
        "/api/v1/companies/current/branding",
        {"expected_version": version, "product_name": "Alpha ProjectOS", "primary_color": "#123456"},
        format="json",
        headers=auth_headers(pair, company),
    )
    assert changed.status_code == 200
    assert changed.data["product_name"] == "Alpha ProjectOS"
    assert changed.data["primary_color"] == "#123456"
    assert changed.data["version"] == version + 1


def test_public_domain_resolution_returns_brand_only_for_active_mapping(api_client, company_factory):
    company = company_factory(display_name="Domain Builders")
    CompanyBrandProfile.objects.create(company=company, product_name="Domain Build", tagline="Build with clarity")
    TenantDomain.objects.create(
        company=company,
        domain="erp.domain-builders.test",
        domain_type=TenantDomain.DomainType.CUSTOM_DOMAIN,
        status=TenantDomain.Status.ACTIVE,
        verified_at=timezone.now(),
        activated_at=timezone.now(),
        ssl_status=TenantDomain.SslStatus.PENDING,
    )

    response = api_client.get("/api/v1/companies/domain/resolve?host=erp.domain-builders.test")
    assert response.status_code == 200
    assert response.data["company"]["public_id"] == str(company.public_id)
    assert response.data["branding"]["product_name"] == "Domain Build"
    assert "legal_name" not in response.data["company"]
    assert "verification_record_name" not in response.data["domain"]
    assert "verification_record_value" not in response.data["domain"]
    assert "support_email" not in response.data["branding"]
    assert "document_footer" not in response.data["branding"]

    TenantDomain.objects.filter(company=company).update(status=TenantDomain.Status.SUSPENDED)
    denied = api_client.get("/api/v1/companies/domain/resolve?host=erp.domain-builders.test")
    assert denied.status_code == 404
