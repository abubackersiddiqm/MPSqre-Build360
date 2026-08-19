from __future__ import annotations

from django.conf import settings
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class PlatformOperator(PublicIdModel, TimestampedModel):
    """Global control-plane authorization independent of tenant membership."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="accessops_platform_operator",
    )
    operator_type_code = models.CharField(max_length=100, default="PLATFORM_OPERATOR")
    is_active = models.BooleanField(default=True)
    created_by_public_id = models.UUIDField(null=True, blank=True)
    last_access_review_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "accessops_platform_operator"
        indexes = [
            models.Index(fields=["is_active", "operator_type_code"], name="accessops_operator_active_idx"),
        ]


class CompanyAccessProfile(PublicIdModel, TimestampedModel):
    """Control-plane metadata that does not mutate the tenant-owned company table."""

    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="accessops_profile",
    )
    plan_code = models.CharField(max_length=100, blank=True)
    onboarding_status_code = models.CharField(max_length=100, default="PENDING_ADMIN")
    primary_admin_email = models.EmailField(max_length=254, blank=True)
    created_by_public_id = models.UUIDField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    setup_completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "accessops_company_profile"
        indexes = [
            models.Index(
                fields=["onboarding_status_code", "created_at"],
                name="accessops_company_onboard_idx",
            ),
        ]


class AccessInvitation(PublicIdModel, TimestampedModel):
    """Hashed, revocable invitation for a company membership and optional employee profile."""

    class DeliveryStatus(models.TextChoices):
        NOT_ATTEMPTED = "NOT_ATTEMPTED", "Not attempted"
        LOCAL_PREVIEW = "LOCAL_PREVIEW", "Local preview"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="accessops_invitations",
    )
    email = models.EmailField(max_length=254)
    display_name = models.CharField(max_length=200)
    invitation_type_code = models.CharField(max_length=100, default="EMPLOYEE")
    token_hash = models.CharField(max_length=64, unique=True)
    token_hint = models.CharField(max_length=12, blank=True)
    role_public_ids = models.JSONField(default=list)
    employee_number = models.CharField(max_length=50, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    invited_by_public_id = models.UUIDField()
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    delivery_status_code = models.CharField(
        max_length=30,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.NOT_ATTEMPTED,
    )
    delivery_attempted_at = models.DateTimeField(null=True, blank=True)
    delivery_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_error_code = models.CharField(max_length=120, blank=True)
    delivery_brand_snapshot = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "accessops_invitation"
        indexes = [
            models.Index(
                fields=["company", "email", "expires_at"],
                name="accessops_invite_company_idx",
            ),
            models.Index(
                fields=["company", "accepted_at", "revoked_at"],
                name="accessops_invite_state_idx",
            ),
        ]
