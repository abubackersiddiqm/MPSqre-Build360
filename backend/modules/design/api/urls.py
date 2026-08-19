from django.urls import path

from .views import (
    DesignDocumentListCreateView,
    DesignIssueCloseView,
    DesignIssueListCreateView,
    DesignReviewDecisionView,
    DesignReviewListCreateView,
    DesignSummaryView,
    DesignTransmittalListCreateView,
    DesignVersionDetailView,
    DesignVersionListCreateView,
    DesignVersionTransitionView,
)

urlpatterns = [
    path("summary", DesignSummaryView.as_view(), name="design-summary"),
    path("documents", DesignDocumentListCreateView.as_view(), name="design-documents"),
    path(
        "documents/<uuid:public_id>/versions",
        DesignVersionListCreateView.as_view(),
        name="design-versions",
    ),
    path("versions/<uuid:public_id>", DesignVersionDetailView.as_view(), name="design-version"),
    path(
        "versions/<uuid:public_id>/transition",
        DesignVersionTransitionView.as_view(),
        name="design-version-transition",
    ),
    path(
        "versions/<uuid:public_id>/reviews",
        DesignReviewListCreateView.as_view(),
        name="design-reviews",
    ),
    path(
        "reviews/<uuid:public_id>/decide",
        DesignReviewDecisionView.as_view(),
        name="design-review-decision",
    ),
    path("issues", DesignIssueListCreateView.as_view(), name="design-issues"),
    path(
        "issues/<uuid:public_id>/close",
        DesignIssueCloseView.as_view(),
        name="design-issue-close",
    ),
    path(
        "transmittals",
        DesignTransmittalListCreateView.as_view(),
        name="design-transmittals",
    ),
]
