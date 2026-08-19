from django.urls import path

from .views import (
    ActivityCreateView,
    ActivityTransitionView,
    AssessmentCreateView,
    AssessmentTransitionView,
    DisclosureCreateView,
    DisclosureTransitionView,
    FactorCreateView,
    InitiativeCreateView,
    InitiativeTransitionView,
    InventoryCreateView,
    InventoryTransitionView,
    OverviewView,
    ResourceCreateView,
    TargetCreateView,
    TargetTransitionView,
    WasteCreateView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="sustainability-overview"),
    path("factors", FactorCreateView.as_view(), name="sustainability-factor-create"),
    path("activities", ActivityCreateView.as_view(), name="sustainability-activity-create"),
    path("activities/<uuid:activity_id>/transition", ActivityTransitionView.as_view(), name="sustainability-activity-transition"),
    path("inventories", InventoryCreateView.as_view(), name="sustainability-inventory-create"),
    path("inventories/<uuid:inventory_id>/transition", InventoryTransitionView.as_view(), name="sustainability-inventory-transition"),
    path("resources", ResourceCreateView.as_view(), name="sustainability-resource-create"),
    path("waste", WasteCreateView.as_view(), name="sustainability-waste-create"),
    path("targets", TargetCreateView.as_view(), name="sustainability-target-create"),
    path("targets/<uuid:target_id>/transition", TargetTransitionView.as_view(), name="sustainability-target-transition"),
    path("initiatives", InitiativeCreateView.as_view(), name="sustainability-initiative-create"),
    path("initiatives/<uuid:initiative_id>/transition", InitiativeTransitionView.as_view(), name="sustainability-initiative-transition"),
    path("assessments", AssessmentCreateView.as_view(), name="sustainability-assessment-create"),
    path("assessments/<uuid:assessment_id>/transition", AssessmentTransitionView.as_view(), name="sustainability-assessment-transition"),
    path("disclosures", DisclosureCreateView.as_view(), name="sustainability-disclosure-create"),
    path("disclosures/<uuid:disclosure_id>/transition", DisclosureTransitionView.as_view(), name="sustainability-disclosure-transition"),
]
