from django.urls import path

from modules.commercialops.api.views import (
    CommercialApprovalDecisionView,
    CommercialApprovalListCreateView,
    CommercialClaimListCreateView,
    CommercialContractListCreateView,
    CommercialOverviewView,
    CommercialPolicyListCreateView,
    CommercialRiskListCreateView,
    CommercialRiskResolveView,
    CommercialTransitionView,
    ContractMilestoneListCreateView,
    ExtensionOfTimeListCreateView,
    PaymentApplicationListCreateView,
    VariationOrderListCreateView,
)

urlpatterns = [
    path("overview/", CommercialOverviewView.as_view(), name="commercial-overview"),
    path("policies/", CommercialPolicyListCreateView.as_view(), name="commercial-policies"),
    path("contracts/", CommercialContractListCreateView.as_view(), name="commercial-contracts"),
    path("milestones/", ContractMilestoneListCreateView.as_view(), name="commercial-milestones"),
    path("variations/", VariationOrderListCreateView.as_view(), name="commercial-variations"),
    path("payments/", PaymentApplicationListCreateView.as_view(), name="commercial-payments"),
    path("claims/", CommercialClaimListCreateView.as_view(), name="commercial-claims"),
    path("extensions-of-time/", ExtensionOfTimeListCreateView.as_view(), name="commercial-eot"),
    path("approvals/", CommercialApprovalListCreateView.as_view(), name="commercial-approvals"),
    path("approvals/<uuid:approval_id>/decision/", CommercialApprovalDecisionView.as_view(), name="commercial-approval-decision"),
    path("risks/", CommercialRiskListCreateView.as_view(), name="commercial-risks"),
    path("risks/<uuid:risk_id>/resolve/", CommercialRiskResolveView.as_view(), name="commercial-risk-resolve"),
    path("<str:entity_type>/<uuid:record_id>/transition/", CommercialTransitionView.as_view(), name="commercial-transition"),
]
