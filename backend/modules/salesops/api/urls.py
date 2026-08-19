from django.urls import path

from .views import (
    BookingCreateView,
    BookingTransitionView,
    BuyerCreateView,
    CommissionCreateView,
    CommissionTransitionView,
    HandoverCreateView,
    HandoverTransitionView,
    InventoryCreateView,
    MilestoneCreateView,
    OverviewView,
    ReceiptCreateView,
    ReceiptTransitionView,
    ReservationCreateView,
    ReservationTransitionView,
    UnitCreateView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="salesops-overview"),
    path("inventories", InventoryCreateView.as_view(), name="salesops-inventory-create"),
    path("units", UnitCreateView.as_view(), name="salesops-unit-create"),
    path("buyers", BuyerCreateView.as_view(), name="salesops-buyer-create"),
    path("reservations", ReservationCreateView.as_view(), name="salesops-reservation-create"),
    path("reservations/<uuid:reservation_id>/transition", ReservationTransitionView.as_view(), name="salesops-reservation-transition"),
    path("bookings", BookingCreateView.as_view(), name="salesops-booking-create"),
    path("bookings/<uuid:booking_id>/transition", BookingTransitionView.as_view(), name="salesops-booking-transition"),
    path("milestones", MilestoneCreateView.as_view(), name="salesops-milestone-create"),
    path("receipts", ReceiptCreateView.as_view(), name="salesops-receipt-create"),
    path("receipts/<uuid:receipt_id>/transition", ReceiptTransitionView.as_view(), name="salesops-receipt-transition"),
    path("commissions", CommissionCreateView.as_view(), name="salesops-commission-create"),
    path("commissions/<uuid:commission_id>/transition", CommissionTransitionView.as_view(), name="salesops-commission-transition"),
    path("handovers", HandoverCreateView.as_view(), name="salesops-handover-create"),
    path("handovers/<uuid:handover_id>/transition", HandoverTransitionView.as_view(), name="salesops-handover-transition"),
]
