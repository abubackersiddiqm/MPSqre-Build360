from django.urls import path

from modules.finance.api.views import (
    AdjustmentListCreateView,
    BudgetListCreateView,
    BudgetTransitionView,
    FinancePolicyView,
    FinanceSummaryView,
    InvoiceListCreateView,
    InvoiceTransitionView,
    LedgerListView,
    PaymentListCreateView,
    PaymentTransitionView,
    PeriodListCreateView,
    PeriodLockView,
    StageListView,
    VariationListCreateView,
    VariationTransitionView,
)

urlpatterns = [
    path("summary", FinanceSummaryView.as_view()),
    path("policy", FinancePolicyView.as_view()),
    path("stages", StageListView.as_view()),
    path("periods", PeriodListCreateView.as_view()),
    path("periods/<uuid:public_id>/lock", PeriodLockView.as_view()),
    path("budgets", BudgetListCreateView.as_view()),
    path("budgets/<uuid:public_id>/transition", BudgetTransitionView.as_view()),
    path("variations", VariationListCreateView.as_view()),
    path("variations/<uuid:public_id>/transition", VariationTransitionView.as_view()),
    path("invoices", InvoiceListCreateView.as_view()),
    path("invoices/<uuid:public_id>/transition", InvoiceTransitionView.as_view()),
    path("payments", PaymentListCreateView.as_view()),
    path("payments/<uuid:public_id>/transition", PaymentTransitionView.as_view()),
    path("adjustments", AdjustmentListCreateView.as_view()),
    path("ledger", LedgerListView.as_view()),
]
