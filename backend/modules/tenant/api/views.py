from rest_framework.request import Request
from rest_framework.response import Response

from modules.subscription.application.feature_control import feature_enabled, feature_matrix
from modules.tenant.models import CompanyBrandProfile, TenantDomain

from .base import TenantScopedAPIView


def _company_branding(company) -> dict[str, object]:
    if not feature_enabled(company=company, code="tenant.white_label"):
        return {
            "product_name": "MPSqre Build360",
            "tagline": "Construction Operating System",
            "logo_url": "",
            "compact_logo_url": "",
            "favicon_url": "",
            "primary_color": "#174D3C",
            "accent_color": "#0F766E",
            "sidebar_style": CompanyBrandProfile.SidebarStyle.LIGHT,
            "powered_by_build360": True,
            "version": 1,
        }
    brand = CompanyBrandProfile.objects.filter(company=company).first()
    if brand is None:
        return {
            "product_name": company.display_name,
            "tagline": "Construction Operating System",
            "logo_url": "",
            "compact_logo_url": "",
            "favicon_url": "",
            "primary_color": "#174D3C",
            "accent_color": "#0F766E",
            "sidebar_style": CompanyBrandProfile.SidebarStyle.LIGHT,
            "powered_by_build360": True,
            "version": 1,
        }
    return {
        "product_name": brand.product_name,
        "tagline": brand.tagline,
        "logo_url": "/api/public-brand-assets/logo" if brand.logo_file_public_id else brand.logo_url,
        "logo_file_public_id": str(brand.logo_file_public_id) if brand.logo_file_public_id else None,
        "compact_logo_url": "/api/public-brand-assets/compact_logo" if brand.compact_logo_file_public_id else brand.compact_logo_url,
        "compact_logo_file_public_id": str(brand.compact_logo_file_public_id) if brand.compact_logo_file_public_id else None,
        "favicon_url": "/api/public-brand-assets/favicon" if brand.favicon_file_public_id else brand.favicon_url,
        "favicon_file_public_id": str(brand.favicon_file_public_id) if brand.favicon_file_public_id else None,
        "primary_color": brand.primary_color,
        "accent_color": brand.accent_color,
        "sidebar_style": brand.sidebar_style,
        "powered_by_build360": brand.powered_by_build360,
        "version": brand.version,
    }


class CurrentCompanyView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        company = self.tenant_context.company
        primary_domain = TenantDomain.objects.filter(
            company=company,
            status=TenantDomain.Status.ACTIVE,
            is_primary=True,
        ).first()
        if (
            primary_domain
            and primary_domain.domain_type == TenantDomain.DomainType.CUSTOM_DOMAIN
            and not feature_enabled(company=company, code="tenant.custom_domain")
        ):
            primary_domain = TenantDomain.objects.filter(
                company=company,
                status=TenantDomain.Status.ACTIVE,
                domain_type=TenantDomain.DomainType.PLATFORM_SUBDOMAIN,
            ).first()
        return Response(
            {
                "public_id": str(company.public_id),
                "code": company.code,
                "legal_name": company.legal_name,
                "display_name": company.display_name,
                "locale": company.locale,
                "timezone": company.timezone,
                "currency": company.currency,
                "unit_system_code": company.unit_system_code,
                "fiscal_year_start_month": company.fiscal_year_start_month,
                "branding": _company_branding(company),
                "primary_domain": primary_domain.domain if primary_domain else None,
            }
        )


class EffectiveCapabilitiesView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        permissions = sorted(self.tenant_context.permission_codes())
        matrix = feature_matrix(company=self.tenant_context.company)
        return Response(
            {
                "permissions": permissions,
                "features": {item["code"]: item["enabled"] for item in matrix["items"]},
                "subscription": matrix["subscription"],
            }
        )
