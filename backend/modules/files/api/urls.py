from django.urls import path

from .views import FileDetailView, FileDownloadView, UploadFinalizeView, UploadInitiateView

urlpatterns = [
    path("uploads", UploadInitiateView.as_view(), name="file-upload-initiate"),
    path(
        "uploads/<uuid:version_id>/finalize",
        UploadFinalizeView.as_view(),
        name="file-upload-finalize",
    ),
    path("<uuid:file_id>", FileDetailView.as_view(), name="file-detail"),
    path("<uuid:file_id>/download", FileDownloadView.as_view(), name="file-download"),
]
