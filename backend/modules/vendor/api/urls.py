from django.urls import path

from modules.vendor.api.views import (
    SupplyStageListCreateView,
    VendorListCreateView,
    VendorQualifyView,
    VendorSummaryView,
    VendorTransitionView,
)

urlpatterns = [
    path("summary", VendorSummaryView.as_view()),
    path("stages", SupplyStageListCreateView.as_view()),
    path("items", VendorListCreateView.as_view()),
    path("items/<uuid:public_id>/qualify", VendorQualifyView.as_view()),
    path("items/<uuid:public_id>/transition", VendorTransitionView.as_view()),
]
