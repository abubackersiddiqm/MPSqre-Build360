from django.urls import path

from modules.notifications.api.views import (
    NotificationListCreateView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationSummaryView,
    PreferenceListUpdateView,
    RuleListCreateView,
)

urlpatterns = [
    path("summary", NotificationSummaryView.as_view()),
    path("items", NotificationListCreateView.as_view()),
    path("items/read-all", NotificationReadAllView.as_view()),
    path("items/<uuid:public_id>/read", NotificationReadView.as_view()),
    path("preferences", PreferenceListUpdateView.as_view()),
    path("rules", RuleListCreateView.as_view()),
]
