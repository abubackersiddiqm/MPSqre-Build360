from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    SessionListView,
    SessionRevokeView,
)

urlpatterns = [
    path("token", LoginView.as_view(), name="auth-token"),
    path("password-reset/request", PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("password-reset/confirm", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="auth-me"),
    path("sessions", SessionListView.as_view(), name="auth-sessions"),
    path(
        "sessions/<uuid:session_id>/revoke",
        SessionRevokeView.as_view(),
        name="auth-session-revoke",
    ),
]

