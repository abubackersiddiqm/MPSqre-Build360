
from django.urls import path

from modules.reporting.api.views import (
    MetricListCreateView,
    ReportDownloadView,
    ReportingSummaryView,
    ReportRunListCreateView,
    SavedReportListCreateView,
)

urlpatterns = [
    path("summary", ReportingSummaryView.as_view()),
    path("metrics", MetricListCreateView.as_view()),
    path("saved", SavedReportListCreateView.as_view()),
    path("runs", ReportRunListCreateView.as_view()),
    path("runs/<uuid:public_id>/download", ReportDownloadView.as_view()),
]
