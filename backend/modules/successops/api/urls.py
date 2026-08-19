from django.urls import path

from modules.successops.api.views import (
    AdoptionSnapshotListCreateView,
    InvoiceIssueView,
    InvoiceListCreateView,
    PaymentListCreateView,
    SuccessopsPortfolioView,
    SuccessopsSummaryView,
    SuccessPlanListCreateView,
    SupportTicketListCreateView,
    SupportTicketTransitionView,
)

urlpatterns = [
    path("summary", SuccessopsSummaryView.as_view(), name="successops-summary"),
    path("portfolio", SuccessopsPortfolioView.as_view(), name="successops-portfolio"),
    path("tickets", SupportTicketListCreateView.as_view(), name="successops-tickets"),
    path(
        "tickets/<uuid:public_id>/transition",
        SupportTicketTransitionView.as_view(),
        name="successops-ticket-transition",
    ),
    path("invoices", InvoiceListCreateView.as_view(), name="successops-invoices"),
    path(
        "invoices/<uuid:public_id>/issue",
        InvoiceIssueView.as_view(),
        name="successops-invoice-issue",
    ),
    path("payments", PaymentListCreateView.as_view(), name="successops-payments"),
    path("plans", SuccessPlanListCreateView.as_view(), name="successops-plans"),
    path(
        "adoption-snapshots",
        AdoptionSnapshotListCreateView.as_view(),
        name="successops-adoption",
    ),
]
