
from django.urls import path

from modules.dataops.api.views import (
    DataopsSummaryView,
    ImportCommitView,
    ImportJobDetailView,
    ImportJobListCreateView,
    PrivacyListCreateView,
    PrivacyResolveView,
    RecoveryCompleteView,
    RecoveryListCreateView,
    RetentionListCreateView,
    TemplateListView,
)

urlpatterns = [
    path("summary", DataopsSummaryView.as_view()),
    path("templates", TemplateListView.as_view()),
    path("imports", ImportJobListCreateView.as_view()),
    path("imports/<uuid:public_id>", ImportJobDetailView.as_view()),
    path("imports/<uuid:public_id>/commit", ImportCommitView.as_view()),
    path("privacy", PrivacyListCreateView.as_view()),
    path("privacy/<uuid:public_id>/resolve", PrivacyResolveView.as_view()),
    path("retention", RetentionListCreateView.as_view()),
    path("recovery", RecoveryListCreateView.as_view()),
    path("recovery/<uuid:public_id>/complete", RecoveryCompleteView.as_view()),
]
