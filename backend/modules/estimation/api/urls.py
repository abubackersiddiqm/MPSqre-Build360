from django.urls import path

from .views import (
    BoqItemListCreateView,
    BoqSectionListCreateView,
    EstimateBaselineListView,
    EstimateDetailView,
    EstimateListCreateView,
    EstimateVersionBaselineView,
    EstimateVersionListCreateView,
    EstimateVersionTransitionView,
    EstimationSummaryView,
)

urlpatterns = [
    path("summary", EstimationSummaryView.as_view(), name="estimation-summary"),
    path("estimates", EstimateListCreateView.as_view(), name="estimates"),
    path("estimates/<uuid:public_id>", EstimateDetailView.as_view(), name="estimate-detail"),
    path(
        "estimates/<uuid:public_id>/versions",
        EstimateVersionListCreateView.as_view(),
        name="estimate-versions",
    ),
    path(
        "estimates/<uuid:public_id>/baselines",
        EstimateBaselineListView.as_view(),
        name="estimate-baselines",
    ),
    path(
        "versions/<uuid:public_id>/transition",
        EstimateVersionTransitionView.as_view(),
        name="estimate-version-transition",
    ),
    path(
        "versions/<uuid:public_id>/baseline",
        EstimateVersionBaselineView.as_view(),
        name="estimate-version-baseline",
    ),
    path(
        "versions/<uuid:public_id>/sections",
        BoqSectionListCreateView.as_view(),
        name="boq-sections",
    ),
    path(
        "versions/<uuid:public_id>/items",
        BoqItemListCreateView.as_view(),
        name="boq-items",
    ),
]
