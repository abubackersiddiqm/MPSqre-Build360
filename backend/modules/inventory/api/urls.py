from django.urls import path

from modules.inventory.api.views import (
    BalanceListView,
    InventorySummaryView,
    ItemListCreateView,
    LedgerListView,
    MovementCreateView,
    WarehouseListCreateView,
)

urlpatterns=[path("summary",InventorySummaryView.as_view()),path("items",ItemListCreateView.as_view()),path("warehouses",WarehouseListCreateView.as_view()),path("balances",BalanceListView.as_view()),path("movements",MovementCreateView.as_view()),path("ledger",LedgerListView.as_view())]
