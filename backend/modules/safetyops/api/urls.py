from django.urls import path

from modules.safetyops.api.views import (
    CorrectiveActionListCreateView,
    CorrectiveActionTransitionView,
    PermitToWorkListCreateView,
    PermitToWorkTransitionView,
    SafetyApprovalDecisionView,
    SafetyApprovalListCreateView,
    SafetyIncidentListCreateView,
    SafetyIncidentTransitionView,
    SafetyInspectionListCreateView,
    SafetyObservationListCreateView,
    SafetyObservationTransitionView,
    SafetyOverviewView,
    SafetyPolicyListCreateView,
    SafetyRiskListCreateView,
    SafetyRiskResolveView,
    ToolboxTalkListCreateView,
)

app_name = "safetyops"

urlpatterns = [
    path("overview/", SafetyOverviewView.as_view(), name="overview"),
    path("policies/", SafetyPolicyListCreateView.as_view(), name="policies"),
    path("observations/", SafetyObservationListCreateView.as_view(), name="observations"),
    path("observations/<uuid:observation_id>/transition/", SafetyObservationTransitionView.as_view(), name="observation-transition"),
    path("incidents/", SafetyIncidentListCreateView.as_view(), name="incidents"),
    path("incidents/<uuid:incident_id>/transition/", SafetyIncidentTransitionView.as_view(), name="incident-transition"),
    path("permits/", PermitToWorkListCreateView.as_view(), name="permits"),
    path("permits/<uuid:permit_id>/transition/", PermitToWorkTransitionView.as_view(), name="permit-transition"),
    path("inspections/", SafetyInspectionListCreateView.as_view(), name="inspections"),
    path("toolbox-talks/", ToolboxTalkListCreateView.as_view(), name="toolbox-talks"),
    path("corrective-actions/", CorrectiveActionListCreateView.as_view(), name="corrective-actions"),
    path("corrective-actions/<uuid:action_id>/transition/", CorrectiveActionTransitionView.as_view(), name="action-transition"),
    path("approvals/", SafetyApprovalListCreateView.as_view(), name="approvals"),
    path("approvals/<uuid:approval_id>/decision/", SafetyApprovalDecisionView.as_view(), name="approval-decision"),
    path("risks/", SafetyRiskListCreateView.as_view(), name="risks"),
    path("risks/<uuid:risk_id>/resolve/", SafetyRiskResolveView.as_view(), name="risk-resolve"),
]
