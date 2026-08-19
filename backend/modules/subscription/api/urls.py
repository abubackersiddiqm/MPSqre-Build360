from django.urls import path

from .views import EffectiveEntitlementsView, EntitlementOverrideCreateView

urlpatterns = [
    path("effective", EffectiveEntitlementsView.as_view(), name="effective-entitlements"),
    path("overrides", EntitlementOverrideCreateView.as_view(), name="entitlement-override-create"),
]
