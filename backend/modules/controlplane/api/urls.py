from django.urls import path

from modules.controlplane.api.views import (
    ControlplaneSummaryView,
    OperatorListView,
    PlanListCreateView,
    PlanPublishView,
    PlatformMeView,
    SubscriptionAssignView,
    SubscriptionListView,
    SupportRequestListCreateView,
    TenantLifecycleView,
    TenantListView,
    UsageCollectView,
    UsageListView,
)

urlpatterns = [
    path("me", PlatformMeView.as_view()),
    path("summary", ControlplaneSummaryView.as_view()),
    path("tenants", TenantListView.as_view()),
    path("tenants/<uuid:public_id>/lifecycle", TenantLifecycleView.as_view()),
    path("plans", PlanListCreateView.as_view()),
    path("plans/<uuid:public_id>/publish", PlanPublishView.as_view()),
    path("subscriptions", SubscriptionListView.as_view()),
    path("tenants/<uuid:public_id>/subscription", SubscriptionAssignView.as_view()),
    path("usage", UsageListView.as_view()),
    path("tenants/<uuid:public_id>/usage/collect", UsageCollectView.as_view()),
    path("support-requests", SupportRequestListCreateView.as_view()),
    path("operators", OperatorListView.as_view()),
]
