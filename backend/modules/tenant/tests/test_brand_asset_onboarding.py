from __future__ import annotations

import hashlib

import pytest
from django.utils import timezone

from modules.files.models import FileObject, FileVersion
from modules.tenant.models import CompanyBrandProfile, TenantDomain

pytestmark = pytest.mark.django_db


def auth_headers(pair, company):
    return {"Authorization": f"Bearer {pair.access_token}", "X-Company-Id": str(company.public_id)}


def clean_brand_file(company, user, *, purpose="tenant.brand.logo"):
    file_object = FileObject.objects.create(
        company=company,
        purpose_code=purpose,
        data_class="public_brand",
        created_by_public_id=user.public_id,
    )
    digest = hashlib.sha256(b"brand").hexdigest()
    FileVersion.objects.create(
        file_object=file_object,
        version=1,
        object_key=f"companies/{company.public_id}/{purpose}/{file_object.public_id}/brand.png",
        original_name="brand.png",
        content_type="image/png",
        expected_size_bytes=5,
        actual_size_bytes=5,
        expected_sha256=digest,
        actual_sha256=digest,
        upload_status=FileVersion.UploadStatus.FINALIZED,
        scan_status=FileVersion.ScanStatus.CLEAN,
        created_by_public_id=user.public_id,
        finalized_at=timezone.now(),
        scan_completed_at=timezone.now(),
    )
    return file_object


def test_clean_governed_brand_asset_can_be_attached_and_public_brand_uses_proxy(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory(display_name="Visual Builders")
    user = user_factory()
    permission_grant_factory(user, company, ["tenant.branding.read", "tenant.branding.manage"])
    pair = token_pair_factory(user)
    profile = CompanyBrandProfile.objects.create(company=company, product_name="Visual OS", tagline="Build better")
    file_object = clean_brand_file(company, user)

    attached = api_client.post(
        "/api/v1/companies/current/branding/assets/attach",
        {"expected_version": profile.version, "slot": "logo", "file_public_id": str(file_object.public_id)},
        format="json",
        headers=auth_headers(pair, company),
    )
    assert attached.status_code == 200
    assert attached.data["logo_file_public_id"] == str(file_object.public_id)
    assert attached.data["logo_url"] == "/api/public-brand-assets/logo"

    TenantDomain.objects.create(
        company=company,
        domain="erp.visual-builders.test",
        domain_type=TenantDomain.DomainType.CUSTOM_DOMAIN,
        status=TenantDomain.Status.ACTIVE,
        verified_at=timezone.now(),
        activated_at=timezone.now(),
        ssl_status=TenantDomain.SslStatus.PENDING,
    )
    resolved = api_client.get("/api/v1/companies/domain/resolve?host=erp.visual-builders.test")
    assert resolved.status_code == 200
    assert resolved.data["branding"]["logo_url"] == "/api/public-brand-assets/logo"


def test_brand_asset_attach_rejects_pending_scan(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory()
    user = user_factory()
    permission_grant_factory(user, company, ["tenant.branding.read", "tenant.branding.manage"])
    pair = token_pair_factory(user)
    profile = CompanyBrandProfile.objects.create(company=company, product_name="Pending")
    file_object = clean_brand_file(company, user)
    FileVersion.objects.filter(file_object=file_object).update(scan_status=FileVersion.ScanStatus.PENDING)

    response = api_client.post(
        "/api/v1/companies/current/branding/assets/attach",
        {"expected_version": profile.version, "slot": "logo", "file_public_id": str(file_object.public_id)},
        format="json",
        headers=auth_headers(pair, company),
    )
    assert response.status_code == 400


def test_onboarding_is_derived_from_brand_and_domain_state(
    api_client,
    company_factory,
    user_factory,
    permission_grant_factory,
    token_pair_factory,
):
    company = company_factory(code="READY", display_name="Ready Builders")
    user = user_factory()
    permission_grant_factory(user, company, ["tenant.branding.read"])
    pair = token_pair_factory(user)
    CompanyBrandProfile.objects.create(
        company=company,
        product_name="Ready OS",
        tagline="Construction Operating System",
        logo_url="https://example.test/logo.png",
        sender_name="Ready Builders",
        support_email="support@example.test",
    )
    TenantDomain.objects.create(
        company=company,
        domain="ready.build360.test",
        domain_type=TenantDomain.DomainType.PLATFORM_SUBDOMAIN,
        status=TenantDomain.Status.ACTIVE,
        verified_at=timezone.now(),
        activated_at=timezone.now(),
        ssl_status=TenantDomain.SslStatus.PENDING,
    )
    response = api_client.get("/api/v1/companies/current/onboarding", headers=auth_headers(pair, company))
    assert response.status_code == 200
    assert response.data["completion_percent"] == 100
    assert any(step["code"] == "CUSTOM_DOMAIN" and step["optional"] for step in response.data["steps"])
