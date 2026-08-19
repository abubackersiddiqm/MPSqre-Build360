from django.urls import path

from .views import (
    ApprovalDecisionView,
    ChecklistCompletionView,
    NotificationStateView,
    OfflineDraftDiscardView,
    OfflineDraftSyncView,
    OfflineDraftView,
    OverviewView,
    ProgressView,
    TeamTimesheetDecisionView,
    TimesheetSubmitView,
    TimesheetView,
    WorkTransitionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="mywork-overview"),
    path("work-items/<uuid:work_item_id>/transition", WorkTransitionView.as_view(), name="mywork-transition"),
    path("checklists/<uuid:checklist_id>/complete", ChecklistCompletionView.as_view(), name="mywork-checklist"),
    path("progress", ProgressView.as_view(), name="mywork-progress"),
    path("timesheets", TimesheetView.as_view(), name="mywork-timesheets"),
    path("timesheets/<uuid:timesheet_id>/submit", TimesheetSubmitView.as_view(), name="mywork-timesheet-submit"),
    path("approvals/<uuid:approval_id>/decision", ApprovalDecisionView.as_view(), name="mywork-approval-decision"),
    path("team-timesheets/<uuid:timesheet_id>/decision", TeamTimesheetDecisionView.as_view(), name="mywork-team-timesheet-decision"),
    path("offline-drafts", OfflineDraftView.as_view(), name="mywork-offline-drafts"),
    path("offline-drafts/<uuid:draft_id>/sync", OfflineDraftSyncView.as_view(), name="mywork-offline-sync"),
    path("offline-drafts/<uuid:draft_id>/discard", OfflineDraftDiscardView.as_view(), name="mywork-offline-discard"),
    path("notifications/<uuid:notification_id>/state", NotificationStateView.as_view(), name="mywork-notification-state"),
]
