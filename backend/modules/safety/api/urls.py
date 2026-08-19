from django.urls import path

from modules.safety.api.views import (
    IncidentListCreateView,
    ObservationListCreateView,
    SafetySummaryView,
)

urlpatterns=[path("summary",SafetySummaryView.as_view()),path("incidents",IncidentListCreateView.as_view()),path("observations",ObservationListCreateView.as_view())]
