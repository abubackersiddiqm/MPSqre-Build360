from django.urls import path

from modules.payrollops.api.views import (
    PayrollApprovalDecisionView,
    PayrollApprovalListCreateView,
    PayrollExceptionListView,
    PayrollExceptionResolveView,
    PayrollOverviewView,
    PayrollPeriodListCreateView,
    PayrollPolicyListCreateView,
    PayrollRunLinesView,
    PayrollRunListCreateView,
    PayrollRunTransitionView,
)

app_name = "payrollops"

urlpatterns = [
    path("overview/", PayrollOverviewView.as_view(), name="overview"),
    path("policies/", PayrollPolicyListCreateView.as_view(), name="policies"),
    path("periods/", PayrollPeriodListCreateView.as_view(), name="periods"),
    path("runs/", PayrollRunListCreateView.as_view(), name="runs"),
    path(
        "runs/<uuid:run_id>/transition/",
        PayrollRunTransitionView.as_view(),
        name="run-transition",
    ),
    path(
        "runs/<uuid:run_id>/lines/",
        PayrollRunLinesView.as_view(),
        name="run-lines",
    ),
    path(
        "approvals/",
        PayrollApprovalListCreateView.as_view(),
        name="approvals",
    ),
    path(
        "approvals/<uuid:approval_id>/decide/",
        PayrollApprovalDecisionView.as_view(),
        name="approval-decision",
    ),
    path("exceptions/", PayrollExceptionListView.as_view(), name="exceptions"),
    path(
        "exceptions/<uuid:exception_id>/resolve/",
        PayrollExceptionResolveView.as_view(),
        name="exception-resolve",
    ),
]
