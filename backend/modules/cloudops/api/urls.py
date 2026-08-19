from django.urls import path

from modules.cloudops.api.views import (
    BackupExecutionListCreateView,
    BackupPolicyListCreateView,
    CloudopsPortfolioView,
    CloudopsSummaryView,
    CloudTargetListCreateView,
    CloudTargetTransitionView,
    DeploymentListCreateView,
    DeploymentTransitionView,
    PipelineListCreateView,
    RestoreExerciseListCreateView,
    RestoreExerciseTransitionView,
    SecretPolicyListCreateView,
    SecretRotationView,
)

urlpatterns = [
    path("summary", CloudopsSummaryView.as_view(), name="cloudops-summary"),
    path("portfolio", CloudopsPortfolioView.as_view(), name="cloudops-portfolio"),
    path("targets", CloudTargetListCreateView.as_view(), name="cloudops-targets"),
    path(
        "targets/<uuid:public_id>/transition",
        CloudTargetTransitionView.as_view(),
        name="cloudops-target-transition",
    ),
    path("pipelines", PipelineListCreateView.as_view(), name="cloudops-pipelines"),
    path("deployments", DeploymentListCreateView.as_view(), name="cloudops-deployments"),
    path(
        "deployments/<uuid:public_id>/transition",
        DeploymentTransitionView.as_view(),
        name="cloudops-deployment-transition",
    ),
    path(
        "backup-policies",
        BackupPolicyListCreateView.as_view(),
        name="cloudops-backup-policies",
    ),
    path(
        "backup-executions",
        BackupExecutionListCreateView.as_view(),
        name="cloudops-backup-executions",
    ),
    path(
        "restore-exercises",
        RestoreExerciseListCreateView.as_view(),
        name="cloudops-restore-exercises",
    ),
    path(
        "restore-exercises/<uuid:public_id>/transition",
        RestoreExerciseTransitionView.as_view(),
        name="cloudops-restore-transition",
    ),
    path(
        "secret-policies",
        SecretPolicyListCreateView.as_view(),
        name="cloudops-secret-policies",
    ),
    path(
        "secret-policies/<uuid:public_id>/rotate",
        SecretRotationView.as_view(),
        name="cloudops-secret-rotate",
    ),
]
