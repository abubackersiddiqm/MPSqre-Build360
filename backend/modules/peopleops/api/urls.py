from django.urls import path

from modules.peopleops.api.views import (
    LeaveRequestListCreateView,
    LeaveRequestTransitionView,
    PayrollRunListCreateView,
    PayrollRunTransitionView,
    PeopleopsPortfolioView,
    PeopleopsSummaryView,
    TimesheetListCreateView,
    TimesheetTransitionView,
)

urlpatterns = [
    path("summary", PeopleopsSummaryView.as_view(), name="peopleops-summary"),
    path("portfolio", PeopleopsPortfolioView.as_view(), name="peopleops-portfolio"),
    path("leave-requests", LeaveRequestListCreateView.as_view(), name="peopleops-leave-requests"),
    path("leave-requests/<uuid:public_id>/transition", LeaveRequestTransitionView.as_view(), name="peopleops-leave-transition"),
    path("timesheets", TimesheetListCreateView.as_view(), name="peopleops-timesheets"),
    path("timesheets/<uuid:public_id>/transition", TimesheetTransitionView.as_view(), name="peopleops-timesheet-transition"),
    path("payroll-runs", PayrollRunListCreateView.as_view(), name="peopleops-payroll-runs"),
    path("payroll-runs/<uuid:public_id>/transition", PayrollRunTransitionView.as_view(), name="peopleops-payroll-transition"),
]
