from django.urls import path

from .views import (
    CutoverPlanCreateView,
    CutoverTaskCreateView,
    CutoverTaskTransitionView,
    GateDecisionView,
    GoLiveWaveCreateView,
    GoLiveWaveTransitionView,
    HypercareIssueCreateView,
    HypercareIssueTransitionView,
    MigrationBatchCreateView,
    MigrationBatchTransitionView,
    MigrationIssueCreateView,
    MigrationIssueResolveView,
    OverviewView,
    TrainingCohortCreateView,
    TrainingEnrollmentCreateView,
    TrainingEnrollmentTransitionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="go-live-overview"),
    path("migration-batches", MigrationBatchCreateView.as_view(), name="go-live-migration-batch-create"),
    path("migration-batches/<uuid:batch_id>/transition", MigrationBatchTransitionView.as_view(), name="go-live-migration-batch-transition"),
    path("migration-issues", MigrationIssueCreateView.as_view(), name="go-live-migration-issue-create"),
    path("migration-issues/<uuid:issue_id>/resolve", MigrationIssueResolveView.as_view(), name="go-live-migration-issue-resolve"),
    path("training-cohorts", TrainingCohortCreateView.as_view(), name="go-live-training-cohort-create"),
    path("training-enrollments", TrainingEnrollmentCreateView.as_view(), name="go-live-training-enrollment-create"),
    path("training-enrollments/<uuid:enrollment_id>/transition", TrainingEnrollmentTransitionView.as_view(), name="go-live-training-enrollment-transition"),
    path("cutover-plans", CutoverPlanCreateView.as_view(), name="go-live-cutover-plan-create"),
    path("cutover-tasks", CutoverTaskCreateView.as_view(), name="go-live-cutover-task-create"),
    path("cutover-tasks/<uuid:task_id>/transition", CutoverTaskTransitionView.as_view(), name="go-live-cutover-task-transition"),
    path("waves", GoLiveWaveCreateView.as_view(), name="go-live-wave-create"),
    path("waves/<uuid:wave_id>/transition", GoLiveWaveTransitionView.as_view(), name="go-live-wave-transition"),
    path("hypercare-issues", HypercareIssueCreateView.as_view(), name="go-live-hypercare-create"),
    path("hypercare-issues/<uuid:issue_id>/transition", HypercareIssueTransitionView.as_view(), name="go-live-hypercare-transition"),
    path("gates/<uuid:gate_id>/decision", GateDecisionView.as_view(), name="go-live-gate-decision"),
]
