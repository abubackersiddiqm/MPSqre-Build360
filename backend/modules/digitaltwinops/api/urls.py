from django.urls import path

from .views import (
    AlertTransitionView,
    AssetCreateView,
    AssetTransitionView,
    ClashCreateView,
    ClashTransitionView,
    DeviceCreateView,
    FederationCreateView,
    IssueCreateView,
    IssueTransitionView,
    ModelCreateView,
    OverviewView,
    RevisionCreateView,
    RevisionTransitionView,
    TelemetryCreateView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="digital-twin-overview"),
    path("models", ModelCreateView.as_view(), name="digital-twin-model-create"),
    path("revisions", RevisionCreateView.as_view(), name="digital-twin-revision-create"),
    path("revisions/<uuid:revision_id>/transition", RevisionTransitionView.as_view(), name="digital-twin-revision-transition"),
    path("federations", FederationCreateView.as_view(), name="digital-twin-federation-create"),
    path("clashes", ClashCreateView.as_view(), name="digital-twin-clash-create"),
    path("clashes/<uuid:clash_id>/transition", ClashTransitionView.as_view(), name="digital-twin-clash-transition"),
    path("issues", IssueCreateView.as_view(), name="digital-twin-issue-create"),
    path("issues/<uuid:issue_id>/transition", IssueTransitionView.as_view(), name="digital-twin-issue-transition"),
    path("devices", DeviceCreateView.as_view(), name="digital-twin-device-create"),
    path("telemetry", TelemetryCreateView.as_view(), name="digital-twin-telemetry-create"),
    path("alerts/<uuid:alert_id>/transition", AlertTransitionView.as_view(), name="digital-twin-alert-transition"),
    path("assets", AssetCreateView.as_view(), name="digital-twin-asset-create"),
    path("assets/<uuid:asset_id>/transition", AssetTransitionView.as_view(), name="digital-twin-asset-transition"),
]
