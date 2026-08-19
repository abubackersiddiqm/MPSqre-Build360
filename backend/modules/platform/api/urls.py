from django.urls import path

from .audit import AuditEventListView
from .health import LiveView, ReadyView

urlpatterns = [
    path("health/live", LiveView.as_view(), name="health-live"),
    path("health/ready", ReadyView.as_view(), name="health-ready"),
    path("audit/events", AuditEventListView.as_view(), name="audit-events"),
]
