from django.urls import path

from .views import (
    CaseCreateView,
    CaseTransitionView,
    ChargeCreateView,
    InvoiceCreateView,
    InvoiceTransitionView,
    LeaseCreateView,
    LeaseTransitionView,
    OccupancyCreateView,
    OccupancyTransitionView,
    OverviewView,
    PropertyCreateView,
    TenantCreateView,
    UnitCreateView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="leaseops-overview"),
    path("properties", PropertyCreateView.as_view(), name="leaseops-property-create"),
    path("units", UnitCreateView.as_view(), name="leaseops-unit-create"),
    path("tenants", TenantCreateView.as_view(), name="leaseops-tenant-create"),
    path("leases", LeaseCreateView.as_view(), name="leaseops-lease-create"),
    path("leases/<uuid:lease_id>/transition", LeaseTransitionView.as_view(), name="leaseops-lease-transition"),
    path("charges", ChargeCreateView.as_view(), name="leaseops-charge-create"),
    path("occupancies", OccupancyCreateView.as_view(), name="leaseops-occupancy-create"),
    path("occupancies/<uuid:occupancy_id>/transition", OccupancyTransitionView.as_view(), name="leaseops-occupancy-transition"),
    path("invoices", InvoiceCreateView.as_view(), name="leaseops-invoice-create"),
    path("invoices/<uuid:invoice_id>/transition", InvoiceTransitionView.as_view(), name="leaseops-invoice-transition"),
    path("cases", CaseCreateView.as_view(), name="leaseops-case-create"),
    path("cases/<uuid:case_id>/transition", CaseTransitionView.as_view(), name="leaseops-case-transition"),
]
