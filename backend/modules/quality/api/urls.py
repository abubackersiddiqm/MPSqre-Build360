from django.urls import path

from modules.quality.api.views import (
    InspectionListCreateView,
    InspectionSubmitView,
    NcrListCreateView,
    QualitySummaryView,
    TemplateListCreateView,
)

urlpatterns=[path("summary",QualitySummaryView.as_view()),path("templates",TemplateListCreateView.as_view()),path("inspections",InspectionListCreateView.as_view()),path("inspections/<uuid:public_id>/submit",InspectionSubmitView.as_view()),path("ncrs",NcrListCreateView.as_view())]
