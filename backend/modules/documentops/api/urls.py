from django.urls import path

from modules.documentops.api.views import (
    ControlledDocumentListCreateView,
    ControlledDocumentTransitionView,
    DocumentApprovalDecisionView,
    DocumentApprovalListCreateView,
    DocumentControlOverviewView,
    DocumentControlPolicyListCreateView,
    DocumentDistributionAcknowledgeView,
    DocumentDistributionListCreateView,
    DocumentRevisionListCreateView,
    DocumentRevisionTransitionView,
    DocumentRiskListCreateView,
    DocumentRiskResolveView,
    DocumentTransmittalListCreateView,
    DocumentTransmittalTransitionView,
    RequestForInformationListCreateView,
    RequestForInformationTransitionView,
    TechnicalSubmittalListCreateView,
    TechnicalSubmittalTransitionView,
)

urlpatterns = [
    path("overview/", DocumentControlOverviewView.as_view(), name="document-overview"),
    path("policies/", DocumentControlPolicyListCreateView.as_view(), name="document-policies"),
    path("documents/", ControlledDocumentListCreateView.as_view(), name="documents"),
    path(
        "documents/<uuid:document_id>/transition/",
        ControlledDocumentTransitionView.as_view(),
        name="document-transition",
    ),
    path("revisions/", DocumentRevisionListCreateView.as_view(), name="document-revisions"),
    path(
        "revisions/<uuid:revision_id>/transition/",
        DocumentRevisionTransitionView.as_view(),
        name="revision-transition",
    ),
    path("transmittals/", DocumentTransmittalListCreateView.as_view(), name="transmittals"),
    path(
        "transmittals/<uuid:transmittal_id>/transition/",
        DocumentTransmittalTransitionView.as_view(),
        name="transmittal-transition",
    ),
    path("rfis/", RequestForInformationListCreateView.as_view(), name="rfis"),
    path(
        "rfis/<uuid:rfi_id>/transition/",
        RequestForInformationTransitionView.as_view(),
        name="rfi-transition",
    ),
    path("submittals/", TechnicalSubmittalListCreateView.as_view(), name="submittals"),
    path(
        "submittals/<uuid:submittal_id>/transition/",
        TechnicalSubmittalTransitionView.as_view(),
        name="submittal-transition",
    ),
    path("approvals/", DocumentApprovalListCreateView.as_view(), name="document-approvals"),
    path(
        "approvals/<uuid:approval_id>/decision/",
        DocumentApprovalDecisionView.as_view(),
        name="document-approval-decision",
    ),
    path("distributions/", DocumentDistributionListCreateView.as_view(), name="document-distributions"),
    path(
        "distributions/<uuid:distribution_id>/acknowledge/",
        DocumentDistributionAcknowledgeView.as_view(),
        name="distribution-acknowledge",
    ),
    path("risks/", DocumentRiskListCreateView.as_view(), name="document-risks"),
    path(
        "risks/<uuid:risk_id>/resolve/",
        DocumentRiskResolveView.as_view(),
        name="document-risk-resolve",
    ),
]
