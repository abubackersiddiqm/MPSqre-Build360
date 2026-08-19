from django.urls import path

from modules.workforceops.api.views import (
    CredentialListUpsertView,
    SkillDefinitionListCreateView,
    WorkforceApprovalDecisionView,
    WorkforceApprovalListCreateView,
    WorkforceDemandAssignmentView,
    WorkforceDemandListCreateView,
    WorkforceOverviewView,
    WorkforcePlanListCreateView,
    WorkforcePlanTransitionView,
    WorkforcePolicyListCreateView,
    WorkforceRiskListCreateView,
    WorkforceRiskResolveView,
)

app_name = "workforceops"

urlpatterns = [
    path("overview/", WorkforceOverviewView.as_view(), name="overview"),
    path("policies/", WorkforcePolicyListCreateView.as_view(), name="policies"),
    path("skills/", SkillDefinitionListCreateView.as_view(), name="skills"),
    path("plans/", WorkforcePlanListCreateView.as_view(), name="plans"),
    path("demands/", WorkforceDemandListCreateView.as_view(), name="demands"),
    path(
        "plans/<uuid:plan_id>/transition/",
        WorkforcePlanTransitionView.as_view(),
        name="plan-transition",
    ),
    path(
        "demands/<uuid:demand_id>/assignments/",
        WorkforceDemandAssignmentView.as_view(),
        name="demand-assignment",
    ),
    path("credentials/", CredentialListUpsertView.as_view(), name="credentials"),
    path("approvals/", WorkforceApprovalListCreateView.as_view(), name="approvals"),
    path(
        "approvals/<uuid:approval_id>/decide/",
        WorkforceApprovalDecisionView.as_view(),
        name="approval-decision",
    ),
    path("risks/", WorkforceRiskListCreateView.as_view(), name="risks"),
    path(
        "risks/<uuid:risk_id>/resolve/",
        WorkforceRiskResolveView.as_view(),
        name="risk-resolve",
    ),
]
