from django.urls import path

from .views import (
    ContactInviteView,
    GrantCreateView,
    InternalDecisionView,
    InternalMessageView,
    ItemCreateView,
    OverviewView,
    PartnerCreateView,
    PartnerDecisionView,
    PartnerMessageView,
    PartnerOverviewView,
    PartnerSubmissionView,
)

urlpatterns = [
    path("overview", OverviewView.as_view(), name="collaboration-overview"),
    path("partners", PartnerCreateView.as_view(), name="collaboration-partner-create"),
    path("partners/<uuid:partner_id>/invite", ContactInviteView.as_view(), name="collaboration-contact-invite"),
    path("grants", GrantCreateView.as_view(), name="collaboration-grant-create"),
    path("items", ItemCreateView.as_view(), name="collaboration-item-create"),
    path("items/<uuid:item_id>/decision", InternalDecisionView.as_view(), name="collaboration-item-decision"),
    path("items/<uuid:item_id>/messages", InternalMessageView.as_view(), name="collaboration-item-message"),
    path("partner/overview", PartnerOverviewView.as_view(), name="partner-collaboration-overview"),
    path("partner/items/<uuid:item_id>/submissions", PartnerSubmissionView.as_view(), name="partner-collaboration-submit"),
    path("partner/items/<uuid:item_id>/decision", PartnerDecisionView.as_view(), name="partner-collaboration-decision"),
    path("partner/items/<uuid:item_id>/messages", PartnerMessageView.as_view(), name="partner-collaboration-message"),
]
