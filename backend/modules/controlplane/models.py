from __future__ import annotations

from collections.abc import Iterable
from typing import NoReturn

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.identity.models import Permission
from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class PlatformRole(PublicIdModel, TimestampedModel):
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "controlplane_platform_role"
        ordering = ["code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="cp_role_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="cp_role_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["code", "retired_at", "effective_from"],
                name="cp_role_active_idx",
            )
        ]


class PlatformRolePermission(PublicIdModel):
    role = models.ForeignKey(
        PlatformRole,
        on_delete=models.PROTECT,
        related_name="permission_grants",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="platform_role_grants",
    )

    class Meta:
        db_table = "controlplane_role_permission"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="cp_role_perm_uq",
            )
        ]


class PlatformOperatorAssignment(PublicIdModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="platform_operator_assignments",
    )
    role = models.ForeignKey(
        PlatformRole,
        on_delete=models.PROTECT,
        related_name="operator_assignments",
    )
    assigned_by_public_id = models.UUIDField()
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "controlplane_operator_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "effective_from"],
                name="cp_operator_assign_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="cp_operator_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "suspended_at", "effective_from"],
                name="cp_operator_active_idx",
            )
        ]


class TenantAccount(PublicIdModel, TimestampedModel):
    class LifecycleStatus(models.TextChoices):
        PILOT = "pilot", "Pilot"
        ACTIVE = "active", "Active"
        GRACE = "grace", "Grace"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    class OnboardingStatus(models.TextChoices):
        DISCOVERY = "discovery", "Discovery"
        CONFIGURATION = "configuration", "Configuration"
        DATA_MIGRATION = "data_migration", "Data migration"
        TRAINING = "training", "Training"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        COMPLETE = "complete", "Complete"

    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="controlplane_account",
    )
    lifecycle_status = models.CharField(
        max_length=20,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.PILOT,
    )
    onboarding_status = models.CharField(
        max_length=24,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.DISCOVERY,
    )
    segment_code = models.CharField(max_length=100, blank=True)
    deployment_region = models.CharField(max_length=100, blank=True)
    data_residency = models.CharField(max_length=100, blank=True)
    pilot_started_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    grace_until = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    lifecycle_reason = models.CharField(max_length=500, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "controlplane_tenant_account"
        ordering = ["company__display_name"]
        indexes = [
            models.Index(
                fields=["lifecycle_status", "onboarding_status"],
                name="cp_tenant_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.lifecycle_status == self.LifecycleStatus.GRACE and not self.grace_until:
            raise ValidationError("A grace tenant requires a grace-until timestamp")
        if self.lifecycle_status == self.LifecycleStatus.SUSPENDED and not self.suspended_at:
            raise ValidationError("A suspended tenant requires a suspension timestamp")
        if self.lifecycle_status == self.LifecycleStatus.CLOSED and not self.closed_at:
            raise ValidationError("A closed tenant requires a closure timestamp")


class TenantUsageSnapshot(PublicIdModel, TimestampedModel):
    tenant_account = models.ForeignKey(
        TenantAccount,
        on_delete=models.PROTECT,
        related_name="usage_snapshots",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    metrics = models.JSONField(default=dict)
    quota_status = models.JSONField(default=dict)
    checksum_sha256 = models.CharField(max_length=64)
    collected_by_public_id = models.UUIDField()
    collected_at = models.DateTimeField()

    class Meta:
        db_table = "controlplane_usage_snapshot"
        ordering = ["-period_end", "tenant_account__company__display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_account", "period_start", "period_end"],
                name="cp_usage_period_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="cp_usage_period_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant_account", "period_end"],
                name="cp_usage_tenant_idx",
            )
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.pk:
            raise ValidationError("Usage snapshots are append-only")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(
        self,
        using: str | None = None,
        keep_parents: bool = False,
    ) -> NoReturn:
        raise ValidationError("Usage snapshots are append-only")


class SupportAccessRequest(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    tenant_account = models.ForeignKey(
        TenantAccount,
        on_delete=models.PROTECT,
        related_name="support_requests",
    )
    operator_assignment = models.ForeignKey(
        PlatformOperatorAssignment,
        on_delete=models.PROTECT,
        related_name="support_requests",
    )
    requested_by_public_id = models.UUIDField()
    reason = models.CharField(max_length=1000)
    scope_codes = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    decided_by_membership_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    revoked_by_public_id = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "controlplane_support_request"
        ordering = ["-requested_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("requested_at")),
                name="cp_support_expiry_valid",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant_account", "status", "expires_at"],
                name="cp_support_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.scope_codes, list) or not self.scope_codes:
            raise ValidationError("Support access requires at least one scope")
        completed = {
            self.Status.APPROVED,
            self.Status.REJECTED,
        }
        if self.status in completed and not self.decided_at:
            raise ValidationError("A decided support request requires a decision timestamp")
        if self.status == self.Status.REVOKED and not self.revoked_at:
            raise ValidationError("A revoked support request requires a revocation timestamp")

