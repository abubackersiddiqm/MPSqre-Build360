from django.urls import path

from .views import (
    CompanyInvitationListCreateView,
    CompanyInvitationRegenerateView,
    CompanyInvitationRevokeView,
    CompanyManagedAccessMatrixView,
    CompanyMembershipManagedAccessHistoryView,
    CompanyMembershipManagedAccessView,
    CompanyMembershipRolesView,
    CompanyMembershipStatusView,
    CompanyOverviewView,
    CompanyPeopleView,
    CompanyRoleListCreateView,
    InvitationAcceptView,
    InvitationPreviewView,
    PlatformCompanyAdminInviteView,
    PlatformCompanyFeatureMatrixView,
    PlatformCompanyListCreateView,
    PlatformCompanyStatusView,
    PlatformOverviewView,
    PlatformPrimaryAdminInvitationView,
    PlatformPrimaryAdminTransferView,
    PlatformSessionView,
)

urlpatterns = [
    path("platform/session", PlatformSessionView.as_view(), name="access-platform-session"),
    path("platform/overview", PlatformOverviewView.as_view(), name="access-platform-overview"),
    path("platform/companies", PlatformCompanyListCreateView.as_view(), name="access-platform-companies"),
    path(
        "platform/companies/<uuid:company_id>/status",
        PlatformCompanyStatusView.as_view(),
        name="access-platform-company-status",
    ),
    path(
        "platform/companies/<uuid:company_id>/feature-matrix",
        PlatformCompanyFeatureMatrixView.as_view(),
        name="access-platform-company-feature-matrix",
    ),
    path(
        "platform/companies/<uuid:company_id>/invite-admin",
        PlatformCompanyAdminInviteView.as_view(),
        name="access-platform-company-invite-admin",
    ),
    path(
        "platform/companies/<uuid:company_id>/primary-admin-invitation",
        PlatformPrimaryAdminInvitationView.as_view(),
        name="access-platform-primary-admin-invitation",
    ),
    path(
        "platform/companies/<uuid:company_id>/primary-admin",
        PlatformPrimaryAdminTransferView.as_view(),
        name="access-platform-primary-admin-transfer",
    ),
    path("company/overview", CompanyOverviewView.as_view(), name="access-company-overview"),
    path("company/people", CompanyPeopleView.as_view(), name="access-company-people"),
    path(
        "company/access-matrix",
        CompanyManagedAccessMatrixView.as_view(),
        name="access-company-managed-access-matrix",
    ),
    path(
        "company/people/<uuid:membership_id>/access-profile",
        CompanyMembershipManagedAccessView.as_view(),
        name="access-company-membership-access-profile",
    ),
    path(
        "company/people/<uuid:membership_id>/access-history",
        CompanyMembershipManagedAccessHistoryView.as_view(),
        name="access-company-membership-access-history",
    ),
    path("company/roles", CompanyRoleListCreateView.as_view(), name="access-company-roles"),
    path(
        "company/invitations",
        CompanyInvitationListCreateView.as_view(),
        name="access-company-invitations",
    ),
    path(
        "company/invitations/<uuid:invitation_id>/regenerate",
        CompanyInvitationRegenerateView.as_view(),
        name="access-company-invitation-regenerate",
    ),
    path(
        "company/invitations/<uuid:invitation_id>/revoke",
        CompanyInvitationRevokeView.as_view(),
        name="access-company-invitation-revoke",
    ),
    path(
        "company/people/<uuid:membership_id>/roles",
        CompanyMembershipRolesView.as_view(),
        name="access-company-membership-roles",
    ),
    path(
        "company/people/<uuid:membership_id>/status",
        CompanyMembershipStatusView.as_view(),
        name="access-company-membership-status",
    ),
    path("invitations/preview", InvitationPreviewView.as_view(), name="access-invitation-preview"),
    path("invitations/accept", InvitationAcceptView.as_view(), name="access-invitation-accept"),
]
