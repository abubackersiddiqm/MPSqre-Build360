from django.urls import path

from modules.adminops.api.views import (
    AdminopsSummaryView,
    EnvironmentListCreateView,
    FeatureFlagDetailView,
    FeatureFlagListCreateView,
    HealthSnapshotListCreateView,
    IncidentDetailView,
    IncidentListCreateView,
    MaintenanceDetailView,
    MaintenanceListCreateView,
    ReleaseCheckListCreateView,
    ReleaseDetailView,
    ReleaseListCreateView,
    RunbookListCreateView,
    ServiceObjectiveListCreateView,
)

urlpatterns = [
    path("summary", AdminopsSummaryView.as_view()),
    path("environments", EnvironmentListCreateView.as_view()),
    path("releases", ReleaseListCreateView.as_view()),
    path("releases/<uuid:public_id>/transition", ReleaseDetailView.as_view()),
    path("checks", ReleaseCheckListCreateView.as_view()),
    path("objectives", ServiceObjectiveListCreateView.as_view()),
    path("health", HealthSnapshotListCreateView.as_view()),
    path("incidents", IncidentListCreateView.as_view()),
    path("incidents/<uuid:public_id>/transition", IncidentDetailView.as_view()),
    path("runbooks", RunbookListCreateView.as_view()),
    path("flags", FeatureFlagListCreateView.as_view()),
    path("flags/<uuid:public_id>", FeatureFlagDetailView.as_view()),
    path("maintenance", MaintenanceListCreateView.as_view()),
    path("maintenance/<uuid:public_id>/transition", MaintenanceDetailView.as_view()),
]
