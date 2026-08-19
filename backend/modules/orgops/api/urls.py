from django.urls import path

from .views import (
    AssignmentView,
    AttendanceView,
    BulkImportView,
    DepartmentView,
    DesignationView,
    EmployeeManagerView,
    EmployeeProfileView,
    LeaveRequestView,
    LeaveReviewView,
    LeaveTypeView,
    OverviewView,
    WorkCalendarView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="peopleorg-overview"),
    path("departments", DepartmentView.as_view(), name="peopleorg-departments"),
    path("designations", DesignationView.as_view(), name="peopleorg-designations"),
    path("work-calendars", WorkCalendarView.as_view(), name="peopleorg-work-calendars"),
    path("people/<uuid:employee_id>/profile", EmployeeProfileView.as_view(), name="peopleorg-profile"),
    path("people/<uuid:employee_id>/manager", EmployeeManagerView.as_view(), name="peopleorg-manager"),
    path("assignments", AssignmentView.as_view(), name="peopleorg-assignments"),
    path("leave-types", LeaveTypeView.as_view(), name="peopleorg-leave-types"),
    path("leave-requests", LeaveRequestView.as_view(), name="peopleorg-leave-requests"),
    path("leave-requests/<uuid:leave_id>/review", LeaveReviewView.as_view(), name="peopleorg-leave-review"),
    path("attendance", AttendanceView.as_view(), name="peopleorg-attendance"),
    path("imports", BulkImportView.as_view(), name="peopleorg-imports"),
]
