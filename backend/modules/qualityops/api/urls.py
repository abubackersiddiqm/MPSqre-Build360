from django.urls import path

from modules.qualityops.api.views import (
    InspectionTestPlanListCreateView,
    InspectionTestPlanTransitionView,
    NonConformanceReportListCreateView,
    NonConformanceReportTransitionView,
    QualityApprovalDecisionView,
    QualityApprovalListCreateView,
    QualityCorrectiveActionListCreateView,
    QualityCorrectiveActionTransitionView,
    QualityInspectionListCreateView,
    QualityInspectionRequestListCreateView,
    QualityInspectionRequestTransitionView,
    QualityOverviewView,
    QualityPolicyListCreateView,
    QualityRiskListCreateView,
    QualityRiskResolveView,
    QualityTestResultListCreateView,
)

app_name = "qualityops"

urlpatterns = [
    path("overview/", QualityOverviewView.as_view(), name="overview"),
    path("policies/", QualityPolicyListCreateView.as_view(), name="policies"),
    path("itps/", InspectionTestPlanListCreateView.as_view(), name="itps"),
    path(
        "itps/<uuid:itp_id>/transition/",
        InspectionTestPlanTransitionView.as_view(),
        name="itp-transition",
    ),
    path(
        "inspection-requests/",
        QualityInspectionRequestListCreateView.as_view(),
        name="inspection-requests",
    ),
    path(
        "inspection-requests/<uuid:inspection_request_id>/transition/",
        QualityInspectionRequestTransitionView.as_view(),
        name="inspection-request-transition",
    ),
    path("inspections/", QualityInspectionListCreateView.as_view(), name="inspections"),
    path("test-results/", QualityTestResultListCreateView.as_view(), name="test-results"),
    path("ncrs/", NonConformanceReportListCreateView.as_view(), name="ncrs"),
    path(
        "ncrs/<uuid:ncr_id>/transition/",
        NonConformanceReportTransitionView.as_view(),
        name="ncr-transition",
    ),
    path(
        "corrective-actions/",
        QualityCorrectiveActionListCreateView.as_view(),
        name="corrective-actions",
    ),
    path(
        "corrective-actions/<uuid:action_id>/transition/",
        QualityCorrectiveActionTransitionView.as_view(),
        name="action-transition",
    ),
    path("approvals/", QualityApprovalListCreateView.as_view(), name="approvals"),
    path(
        "approvals/<uuid:approval_id>/decision/",
        QualityApprovalDecisionView.as_view(),
        name="approval-decision",
    ),
    path("risks/", QualityRiskListCreateView.as_view(), name="risks"),
    path(
        "risks/<uuid:risk_id>/resolve/",
        QualityRiskResolveView.as_view(),
        name="risk-resolve",
    ),
]
