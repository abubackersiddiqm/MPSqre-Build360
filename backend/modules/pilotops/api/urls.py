from django.urls import path

from modules.pilotops.api.views import (
    AdoptionCollectView,
    ChecklistTransitionView,
    GoLiveSignoffView,
    GoLiveTransitionView,
    MasterDataValidateView,
    PilotPortfolioView,
    PilotSummaryView,
    ReadinessAssessView,
    TrainingCompletionView,
)

urlpatterns = [
    path("summary", PilotSummaryView.as_view(), name="pilot-summary"),
    path("portfolio", PilotPortfolioView.as_view(), name="pilot-portfolio"),
    path(
        "checklist/<uuid:public_id>/transition",
        ChecklistTransitionView.as_view(),
        name="pilot-checklist-transition",
    ),
    path(
        "programs/<uuid:program_public_id>/validate-master-data",
        MasterDataValidateView.as_view(),
        name="pilot-master-data-validate",
    ),
    path(
        "training/<uuid:public_id>/complete",
        TrainingCompletionView.as_view(),
        name="pilot-training-complete",
    ),
    path(
        "programs/<uuid:program_public_id>/assess-readiness",
        ReadinessAssessView.as_view(),
        name="pilot-readiness-assess",
    ),
    path(
        "signoffs/<uuid:public_id>/decide",
        GoLiveSignoffView.as_view(),
        name="pilot-signoff-decision",
    ),
    path(
        "go-live/<uuid:public_id>/transition",
        GoLiveTransitionView.as_view(),
        name="pilot-golive-transition",
    ),
    path(
        "programs/<uuid:program_public_id>/collect-adoption",
        AdoptionCollectView.as_view(),
        name="pilot-adoption-collect",
    ),
]
