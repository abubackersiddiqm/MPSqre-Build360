from django.urls import path

from modules.procurement.api.views import (
    ProcurementSummaryView,
    PurchaseOrderListView,
    PurchaseOrderTransitionView,
    QuoteAwardView,
    QuoteListCreateView,
    ReceiptListCreateView,
    ReceiptPostView,
    RequestListCreateView,
    RequestTransitionView,
    RfqListCreateView,
    RfqTransitionView,
)

urlpatterns = [
    path("summary", ProcurementSummaryView.as_view()),
    path("requests", RequestListCreateView.as_view()),
    path(
        "requests/<uuid:public_id>/transition",
        RequestTransitionView.as_view(),
    ),
    path("rfqs", RfqListCreateView.as_view()),
    path("rfqs/<uuid:public_id>/transition", RfqTransitionView.as_view()),
    path("quotes", QuoteListCreateView.as_view()),
    path("quotes/<uuid:public_id>/award", QuoteAwardView.as_view()),
    path("purchase-orders", PurchaseOrderListView.as_view()),
    path(
        "purchase-orders/<uuid:public_id>/transition",
        PurchaseOrderTransitionView.as_view(),
    ),
    path("receipts", ReceiptListCreateView.as_view()),
    path("receipts/<uuid:public_id>/post", ReceiptPostView.as_view()),
]
