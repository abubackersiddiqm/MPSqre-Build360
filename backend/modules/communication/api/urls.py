from django.urls import path

from modules.communication.api.views import (
    CallbackReceiptListView,
    ChannelPolicyListUpdateView,
    CommunicationCancelView,
    CommunicationDispatchView,
    CommunicationRequestListCreateView,
    CommunicationSummaryView,
    ConsentListCreateView,
    InboundCommunicationListView,
    ProviderCallbackView,
    ProviderListCreateView,
    TemplateListCreateView,
    TemplatePublishView,
)

urlpatterns = [
    path("summary", CommunicationSummaryView.as_view()),
    path("policies", ChannelPolicyListUpdateView.as_view()),
    path("providers", ProviderListCreateView.as_view()),
    path("templates", TemplateListCreateView.as_view()),
    path("templates/<uuid:public_id>/publish", TemplatePublishView.as_view()),
    path("consents", ConsentListCreateView.as_view()),
    path("requests", CommunicationRequestListCreateView.as_view()),
    path("requests/<uuid:public_id>/dispatch", CommunicationDispatchView.as_view()),
    path("requests/<uuid:public_id>/cancel", CommunicationCancelView.as_view()),
    path("callbacks", CallbackReceiptListView.as_view()),
    path("inbound", InboundCommunicationListView.as_view()),
    path(
        "provider-callbacks/<uuid:provider_public_id>",
        ProviderCallbackView.as_view(),
    ),
]
