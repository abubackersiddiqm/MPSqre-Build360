from django.urls import path

from modules.equipmentops.api.views import (
    EquipmentApprovalDecisionView,
    EquipmentApprovalListCreateView,
    EquipmentAssetListCreateView,
    EquipmentDeploymentListCreateView,
    EquipmentInspectionListCreateView,
    EquipmentMeterReadingListCreateView,
    EquipmentOverviewView,
    EquipmentPolicyListCreateView,
    EquipmentRiskListCreateView,
    EquipmentRiskResolveView,
    MaintenanceWorkOrderListCreateView,
    MaintenanceWorkOrderTransitionView,
)

app_name = "equipmentops"

urlpatterns = [
    path("overview/", EquipmentOverviewView.as_view(), name="overview"),
    path("policies/", EquipmentPolicyListCreateView.as_view(), name="policies"),
    path("assets/", EquipmentAssetListCreateView.as_view(), name="assets"),
    path("deployments/", EquipmentDeploymentListCreateView.as_view(), name="deployments"),
    path("meter-readings/", EquipmentMeterReadingListCreateView.as_view(), name="meter-readings"),
    path("work-orders/", MaintenanceWorkOrderListCreateView.as_view(), name="work-orders"),
    path(
        "work-orders/<uuid:work_order_id>/transition/",
        MaintenanceWorkOrderTransitionView.as_view(),
        name="work-order-transition",
    ),
    path("inspections/", EquipmentInspectionListCreateView.as_view(), name="inspections"),
    path("approvals/", EquipmentApprovalListCreateView.as_view(), name="approvals"),
    path(
        "approvals/<uuid:approval_id>/decision/",
        EquipmentApprovalDecisionView.as_view(),
        name="approval-decision",
    ),
    path("risks/", EquipmentRiskListCreateView.as_view(), name="risks"),
    path(
        "risks/<uuid:risk_id>/resolve/",
        EquipmentRiskResolveView.as_view(),
        name="risk-resolve",
    ),
]
