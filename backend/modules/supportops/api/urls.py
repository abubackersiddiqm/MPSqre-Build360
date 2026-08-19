from django.urls import path

from .views import (
    ArticleCreateView,
    ArticleTransitionView,
    ChangeCreateView,
    ChangeTransitionView,
    FeedbackCreateView,
    ImprovementCreateView,
    ImprovementTransitionView,
    InteractionCreateView,
    OverviewView,
    ProblemCreateView,
    ProblemTransitionView,
    SLARefreshView,
    TicketCreateView,
    TicketTransitionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="support-overview"),
    path("tickets", TicketCreateView.as_view(), name="support-ticket-create"),
    path("tickets/<uuid:ticket_id>/transition", TicketTransitionView.as_view(), name="support-ticket-transition"),
    path("interactions", InteractionCreateView.as_view(), name="support-interaction-create"),
    path("problems", ProblemCreateView.as_view(), name="support-problem-create"),
    path("problems/<uuid:problem_id>/transition", ProblemTransitionView.as_view(), name="support-problem-transition"),
    path("changes", ChangeCreateView.as_view(), name="support-change-create"),
    path("changes/<uuid:change_id>/transition", ChangeTransitionView.as_view(), name="support-change-transition"),
    path("knowledge", ArticleCreateView.as_view(), name="support-article-create"),
    path("knowledge/<uuid:article_id>/transition", ArticleTransitionView.as_view(), name="support-article-transition"),
    path("feedback", FeedbackCreateView.as_view(), name="support-feedback-create"),
    path("improvements", ImprovementCreateView.as_view(), name="support-improvement-create"),
    path("improvements/<uuid:improvement_id>/transition", ImprovementTransitionView.as_view(), name="support-improvement-transition"),
    path("sla/refresh", SLARefreshView.as_view(), name="support-sla-refresh"),
]
