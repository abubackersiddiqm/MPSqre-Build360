from django.urls import path

from .views import (
    EndpointCreateView,
    GateDecisionView,
    IncidentCreateView,
    IncidentTransitionView,
    OverviewView,
    RegressionCreateView,
    RegressionTransitionView,
    SampleCreateView,
    ScanRunView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="stability-overview"),
    path("endpoints", EndpointCreateView.as_view(), name="stability-endpoint-create"),
    path("samples", SampleCreateView.as_view(), name="stability-sample-create"),
    path("scans", ScanRunView.as_view(), name="stability-scan-run"),
    path("incidents", IncidentCreateView.as_view(), name="stability-incident-create"),
    path("incidents/<uuid:incident_id>/transition", IncidentTransitionView.as_view(), name="stability-incident-transition"),
    path("regressions", RegressionCreateView.as_view(), name="stability-regression-create"),
    path("regressions/<uuid:regression_id>/transition", RegressionTransitionView.as_view(), name="stability-regression-transition"),
    path("gates/<uuid:gate_id>/decision", GateDecisionView.as_view(), name="stability-gate-decision"),
]
