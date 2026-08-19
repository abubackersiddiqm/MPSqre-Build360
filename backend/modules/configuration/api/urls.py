from django.urls import path

from .views import (
    ActiveConfigurationDetailView,
    ActiveConfigurationListView,
    ConfigurationDraftCreateView,
    ConfigurationPublishView,
)

urlpatterns = [
    path("", ActiveConfigurationListView.as_view(), name="configuration-list"),
    path("active/<str:code>", ActiveConfigurationDetailView.as_view(), name="configuration-active"),
    path("drafts", ConfigurationDraftCreateView.as_view(), name="configuration-draft-create"),
    path(
        "<uuid:version_id>/publish",
        ConfigurationPublishView.as_view(),
        name="configuration-publish",
    ),
]
