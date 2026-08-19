from django.urls import path

from .views import (
    ApproveReleaseView,
    BackupCreateView,
    GateDecisionView,
    GateEvidenceAttachmentView,
    OverviewView,
    PublishReleaseView,
    ReadinessRunView,
    ReleaseCreateView,
    TargetCreateView,
    UATEvidenceAttachmentView,
    UATExecutionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="release-readiness-overview"),
    path("targets", TargetCreateView.as_view(), name="release-target-create"),
    path("releases", ReleaseCreateView.as_view(), name="release-candidate-create"),
    path("gates/<uuid:gate_id>/decision", GateDecisionView.as_view(), name="release-gate-decision"),
    path("gates/<uuid:gate_id>/evidence-files", GateEvidenceAttachmentView.as_view(), name="release-gate-evidence-file"),
    path("uat/<uuid:execution_id>/execute", UATExecutionView.as_view(), name="release-uat-execute"),
    path("uat/<uuid:execution_id>/evidence-files", UATEvidenceAttachmentView.as_view(), name="release-uat-evidence-file"),
    path("backups", BackupCreateView.as_view(), name="release-backup-create"),
    path("readiness-runs", ReadinessRunView.as_view(), name="release-readiness-run"),
    path("releases/<uuid:release_id>/approve", ApproveReleaseView.as_view(), name="release-candidate-approve"),
    path("releases/<uuid:release_id>/publish", PublishReleaseView.as_view(), name="release-candidate-publish"),
]
