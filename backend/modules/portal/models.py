
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from modules.platform.models import TenantOwnedModel


class PortalType(models.TextChoices):
    CLIENT = "client", "Client"
    VENDOR = "vendor", "Vendor"


class PortalScopeType(models.TextChoices):
    COMPANY = "company", "Company"
    PROJECT = "project", "Project"
    CUSTOMER = "customer", "Customer"
    VENDOR = "vendor", "Vendor"


class PortalInvitation(TenantOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    email = models.EmailField(max_length=254)
    portal_type = models.CharField(max_length=20, choices=PortalType.choices)
    scope_type = models.CharField(max_length=20, choices=PortalScopeType.choices)
    scope_public_id = models.UUIDField(null=True, blank=True)
    permission_codes = models.JSONField(default=list)
    token_digest = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    invited_by_public_id = models.UUIDField()
    expires_at = models.DateTimeField()
    accepted_by_public_id = models.UUIDField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_by_public_id = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "portal_invitation"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "email", "portal_type", "scope_type", "scope_public_id"],
                condition=Q(status="pending"),
                name="portal_pending_invite_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "expires_at"],
                name="portal_invite_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.scope_type == PortalScopeType.COMPANY and self.scope_public_id is not None:
            raise ValidationError("Company-scoped invitations must not include a scope ID")
        if self.scope_type != PortalScopeType.COMPANY and self.scope_public_id is None:
            raise ValidationError("A non-company portal scope requires a scope ID")
        if not isinstance(self.permission_codes, list) or len(self.permission_codes) > 50:
            raise ValidationError("A portal invitation supports at most 50 permissions")


class PortalAccessGrant(TenantOwnedModel):
    user_public_id = models.UUIDField()
    portal_type = models.CharField(max_length=20, choices=PortalType.choices)
    scope_type = models.CharField(max_length=20, choices=PortalScopeType.choices)
    scope_public_id = models.UUIDField(null=True, blank=True)
    permission_codes = models.JSONField(default=list)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    granted_by_public_id = models.UUIDField()
    revoked_by_public_id = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=500, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "portal_access_grant"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user_public_id", "portal_type", "scope_type", "scope_public_id"],
                condition=Q(revoked_at__isnull=True),
                name="portal_active_grant_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gt=models.F("effective_from")),
                name="portal_grant_range_ok",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "user_public_id", "revoked_at"],
                name="portal_user_grant_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.scope_type == PortalScopeType.COMPANY and self.scope_public_id is not None:
            raise ValidationError("Company-scoped grants must not include a scope ID")
        if self.scope_type != PortalScopeType.COMPANY and self.scope_public_id is None:
            raise ValidationError("A non-company portal scope requires a scope ID")


class PortalShare(TenantOwnedModel):
    class AccessLevel(models.TextChoices):
        VIEW = "view", "View"
        COMMENT = "comment", "Comment"
        SUBMIT = "submit", "Submit"

    grant = models.ForeignKey(
        PortalAccessGrant,
        on_delete=models.PROTECT,
        related_name="shares",
    )
    entity_type = models.CharField(max_length=100)
    entity_public_id = models.UUIDField()
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.VIEW,
    )
    created_by_public_id = models.UUIDField()
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_by_public_id = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "portal_share"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "grant", "entity_type", "entity_public_id"],
                condition=Q(revoked_at__isnull=True),
                name="portal_active_share_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "entity_public_id", "revoked_at"],
                name="portal_share_entity_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.grant_id and self.grant.company_id != self.company_id:
            raise ValidationError("A portal share cannot cross companies")
