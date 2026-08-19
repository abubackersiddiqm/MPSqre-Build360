from django.urls import path

from modules.controlplane.api.views import (
    TenantSupportRequestDecisionView,
    TenantSupportRequestListView,
)

from .branding_views import (
    CurrentBrandingAssetAttachView,
    CurrentBrandingAssetListView,
    CurrentBrandingView,
    CurrentDomainListCreateView,
    CurrentTenantOnboardingView,
    DomainPrimaryView,
    DomainVerifyView,
    PublicBrandAssetView,
    PublicDomainResolveView,
)
from .email_delivery_views import (
    CurrentEmailDeliveryTestView,
    CurrentEmailDeliveryView,
)
from .views import CurrentCompanyView, EffectiveCapabilitiesView

urlpatterns = [
    path("domain/resolve", PublicDomainResolveView.as_view(), name="company-domain-resolve"),
    path("domain/asset", PublicBrandAssetView.as_view(), name="company-domain-asset"),
    path("current/branding", CurrentBrandingView.as_view(), name="company-branding"),
    path("current/email-delivery", CurrentEmailDeliveryView.as_view(), name="company-email-delivery"),
    path("current/email-delivery/test", CurrentEmailDeliveryTestView.as_view(), name="company-email-delivery-test"),
    path("current/branding/assets", CurrentBrandingAssetListView.as_view(), name="company-branding-assets"),
    path("current/branding/assets/attach", CurrentBrandingAssetAttachView.as_view(), name="company-branding-asset-attach"),
    path("current/onboarding", CurrentTenantOnboardingView.as_view(), name="company-onboarding"),
    path("current/domains", CurrentDomainListCreateView.as_view(), name="company-domains"),
    path("current/domains/<uuid:public_id>/verify", DomainVerifyView.as_view(), name="company-domain-verify"),
    path("current/domains/<uuid:public_id>/primary", DomainPrimaryView.as_view(), name="company-domain-primary"),
    path("current", CurrentCompanyView.as_view(), name="company-current"),
    path(
        "current/capabilities",
        EffectiveCapabilitiesView.as_view(),
        name="company-capabilities",
    ),
    path(
        "current/support-requests",
        TenantSupportRequestListView.as_view(),
        name="company-support-requests",
    ),
    path(
        "current/support-requests/<uuid:public_id>/decision",
        TenantSupportRequestDecisionView.as_view(),
        name="company-support-request-decision",
    ),
]
