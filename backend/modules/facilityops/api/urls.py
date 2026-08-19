from django.urls import path

from .views import (
    AssetCreateView,
    AssetTransitionView,
    FacilityCreateView,
    InspectionCreateView,
    InspectionTransitionView,
    LifecycleEventCreateView,
    OverviewView,
    PlanCreateView,
    ServiceRequestCreateView,
    ServiceRequestTransitionView,
    SpaceCreateView,
    WarrantyClaimCreateView,
    WarrantyClaimTransitionView,
    WorkOrderCreateView,
    WorkOrderTransitionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="facility-overview"),
    path("facilities", FacilityCreateView.as_view(), name="facility-create"),
    path("spaces", SpaceCreateView.as_view(), name="facility-space-create"),
    path("assets", AssetCreateView.as_view(), name="facility-asset-create"),
    path("assets/<uuid:asset_id>/transition", AssetTransitionView.as_view(), name="facility-asset-transition"),
    path("maintenance-plans", PlanCreateView.as_view(), name="facility-plan-create"),
    path("service-requests", ServiceRequestCreateView.as_view(), name="facility-request-create"),
    path("service-requests/<uuid:request_id>/transition", ServiceRequestTransitionView.as_view(), name="facility-request-transition"),
    path("work-orders", WorkOrderCreateView.as_view(), name="facility-work-order-create"),
    path("work-orders/<uuid:work_order_id>/transition", WorkOrderTransitionView.as_view(), name="facility-work-order-transition"),
    path("warranty-claims", WarrantyClaimCreateView.as_view(), name="facility-warranty-create"),
    path("warranty-claims/<uuid:claim_id>/transition", WarrantyClaimTransitionView.as_view(), name="facility-warranty-transition"),
    path("inspections", InspectionCreateView.as_view(), name="facility-inspection-create"),
    path("inspections/<uuid:inspection_id>/transition", InspectionTransitionView.as_view(), name="facility-inspection-transition"),
    path("lifecycle-events", LifecycleEventCreateView.as_view(), name="facility-event-create"),
]
