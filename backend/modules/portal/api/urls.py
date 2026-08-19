
from django.urls import path

from modules.portal.api.views import (
    GrantListCreateView,
    GrantRevokeView,
    InvitationAcceptView,
    InvitationDeliveryView,
    InvitationListCreateView,
    MyPortalGrantsView,
    MyPortalSharesView,
    PortalSharedFileDownloadView,
    PortalSummaryView,
    ShareListCreateView,
)

urlpatterns = [
    path("summary", PortalSummaryView.as_view()),
    path("invitations", InvitationListCreateView.as_view()),
    path("invitations/accept", InvitationAcceptView.as_view()),
    path("invitations/<uuid:public_id>/deliver", InvitationDeliveryView.as_view()),
    path("grants", GrantListCreateView.as_view()),
    path("grants/<uuid:public_id>/revoke", GrantRevokeView.as_view()),
    path("shares", ShareListCreateView.as_view()),
    path("me", MyPortalGrantsView.as_view()),
    path("me/shares", MyPortalSharesView.as_view()),
    path("me/shares/<uuid:share_public_id>/download", PortalSharedFileDownloadView.as_view()),
]
