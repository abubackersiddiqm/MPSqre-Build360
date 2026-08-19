from django.urls import path

from modules.labour.api.views import (
    AllocationListCreateView,
    AttendanceListCreateView,
    AttendanceTransitionView,
    LabourSummaryView,
    WorkerListCreateView,
)

urlpatterns = [
    path("summary", LabourSummaryView.as_view(), name="labour-summary"),
    path("workers", WorkerListCreateView.as_view(), name="labour-workers"),
    path("allocations", AllocationListCreateView.as_view(), name="labour-allocations"),
    path("attendance", AttendanceListCreateView.as_view(), name="labour-attendance"),
    path("attendance/<uuid:public_id>/transition", AttendanceTransitionView.as_view(), name="labour-attendance-transition"),
]
