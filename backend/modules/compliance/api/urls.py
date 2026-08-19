from django.urls import path

from modules.compliance.api.views import (
    AccessReviewItemDecisionView,
    AccessReviewListCreateView,
    AccessReviewTransitionView,
    AssessmentListCreateView,
    AssessmentTransitionView,
    CompliancePortfolioView,
    ComplianceSummaryView,
    EvaluationUpdateView,
    ExceptionDecisionView,
    ExceptionListCreateView,
    RiskListCreateView,
    RiskTransitionView,
)

urlpatterns = [
    path("summary", ComplianceSummaryView.as_view(), name="compliance-summary"),
    path("portfolio", CompliancePortfolioView.as_view(), name="compliance-portfolio"),
    path("assessments", AssessmentListCreateView.as_view(), name="compliance-assessments"),
    path(
        "evaluations/<uuid:public_id>/evaluate",
        EvaluationUpdateView.as_view(),
        name="compliance-evaluation",
    ),
    path(
        "assessments/<uuid:public_id>/transition",
        AssessmentTransitionView.as_view(),
        name="compliance-assessment-transition",
    ),
    path("risks", RiskListCreateView.as_view(), name="compliance-risks"),
    path(
        "risks/<uuid:public_id>/transition",
        RiskTransitionView.as_view(),
        name="compliance-risk-transition",
    ),
    path("exceptions", ExceptionListCreateView.as_view(), name="compliance-exceptions"),
    path(
        "exceptions/<uuid:public_id>/decide",
        ExceptionDecisionView.as_view(),
        name="compliance-exception-decision",
    ),
    path(
        "access-reviews",
        AccessReviewListCreateView.as_view(),
        name="compliance-access-reviews",
    ),
    path(
        "access-review-items/<uuid:public_id>/decide",
        AccessReviewItemDecisionView.as_view(),
        name="compliance-access-review-item-decision",
    ),
    path(
        "access-reviews/<uuid:public_id>/transition",
        AccessReviewTransitionView.as_view(),
        name="compliance-access-review-transition",
    ),
]
