from django.urls import path

from modules.equipment.api.views import (
    EquipmentAllocationListCreateView,
    EquipmentListCreateView,
    EquipmentSummaryView,
    MaintenanceListCreateView,
    MeterReadingCreateView,
)

urlpatterns = [
    path("summary", EquipmentSummaryView.as_view(), name="equipment-summary"),
    path("assets", EquipmentListCreateView.as_view(), name="equipment-assets"),
    path("allocations", EquipmentAllocationListCreateView.as_view(), name="equipment-allocations"),
    path("meter-readings", MeterReadingCreateView.as_view(), name="equipment-meter-readings"),
    path("maintenance", MaintenanceListCreateView.as_view(), name="equipment-maintenance"),
]
