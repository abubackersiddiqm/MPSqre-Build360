from django.urls import path

from .views import (
    ApprovalDecisionView,
    ApprovalInboxView,
    UnifiedApprovalCenterView,
    WorkflowDefinitionCreateView,
    WorkflowStartView,
    WorkflowTransitionView,
    WorkflowVersionCreateView,
    WorkflowVersionPublishView,
)

urlpatterns = [
    path("definitions", WorkflowDefinitionCreateView.as_view()),
    path("definitions/<uuid:definition_id>/versions", WorkflowVersionCreateView.as_view()),
    path("versions/<uuid:version_id>/publish", WorkflowVersionPublishView.as_view()),
    path("definitions/<str:definition_code>/instances", WorkflowStartView.as_view()),
    path("instances/<uuid:instance_id>/transitions", WorkflowTransitionView.as_view()),
    path("approvals", ApprovalInboxView.as_view()),
    path("approval-center", UnifiedApprovalCenterView.as_view()),
    path("approvals/<uuid:approval_id>/decision", ApprovalDecisionView.as_view()),
]
