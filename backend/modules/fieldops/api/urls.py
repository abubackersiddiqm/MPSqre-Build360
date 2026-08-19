from django.urls import path

from modules.fieldops.api.views import (
    FieldStageListCreateView,
    FieldSyncSummaryView,
    OfflineOperationListCreateView,
)

urlpatterns = [
    path("summary", FieldSyncSummaryView.as_view(), name="field-summary"),
    path("stages", FieldStageListCreateView.as_view(), name="field-stages"),
    path("offline/operations", OfflineOperationListCreateView.as_view(), name="offline-operations"),
]
