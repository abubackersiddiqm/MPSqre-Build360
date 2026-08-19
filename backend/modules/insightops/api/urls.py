from django.urls import path

from .views import (
    ActionCreateView,
    ActionTransitionView,
    BenefitCreateView,
    BenefitMeasurementCreateView,
    BoardReportCreateView,
    BoardReportTransitionView,
    KPICreateView,
    ObjectiveCreateView,
    ObservationCreateView,
    OverviewView,
    SnapshotCreateView,
    SnapshotTransitionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="insight-overview"),
    path("objectives", ObjectiveCreateView.as_view(), name="insight-objective-create"),
    path("kpis", KPICreateView.as_view(), name="insight-kpi-create"),
    path("observations", ObservationCreateView.as_view(), name="insight-observation-create"),
    path("portfolio-snapshots", SnapshotCreateView.as_view(), name="insight-snapshot-create"),
    path("portfolio-snapshots/<uuid:snapshot_id>/transition", SnapshotTransitionView.as_view(), name="insight-snapshot-transition"),
    path("benefits", BenefitCreateView.as_view(), name="insight-benefit-create"),
    path("benefit-measurements", BenefitMeasurementCreateView.as_view(), name="insight-benefit-measurement-create"),
    path("actions", ActionCreateView.as_view(), name="insight-action-create"),
    path("actions/<uuid:action_id>/transition", ActionTransitionView.as_view(), name="insight-action-transition"),
    path("board-reports", BoardReportCreateView.as_view(), name="insight-board-report-create"),
    path("board-reports/<uuid:report_id>/transition", BoardReportTransitionView.as_view(), name="insight-board-report-transition"),
]
