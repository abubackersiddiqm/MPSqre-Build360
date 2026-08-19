from django.urls import path

from modules.ai.api.views import (
    AISummaryView,
    EvaluationListCreateView,
    ExtractionListCreateView,
    ExtractionReviewView,
    InteractionListCreateView,
    InteractionReviewView,
    PolicyListCreateView,
    ProviderListView,
    RiskDecisionView,
    RiskListScanView,
    ToolActionDecisionView,
    ToolActionListCreateView,
)

urlpatterns = [
    path("summary", AISummaryView.as_view()),
    path("providers", ProviderListView.as_view()),
    path("policies", PolicyListCreateView.as_view()),
    path("interactions", InteractionListCreateView.as_view()),
    path("interactions/<uuid:public_id>/review", InteractionReviewView.as_view()),
    path("extractions", ExtractionListCreateView.as_view()),
    path("extractions/<uuid:public_id>/review", ExtractionReviewView.as_view()),
    path("risks", RiskListScanView.as_view()),
    path("risks/<uuid:public_id>/decision", RiskDecisionView.as_view()),
    path("actions", ToolActionListCreateView.as_view()),
    path("actions/<uuid:public_id>/decision", ToolActionDecisionView.as_view()),
    path("evaluations", EvaluationListCreateView.as_view()),
]
