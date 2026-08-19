from collections.abc import Iterable
from typing import NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class PlanVersion(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    code = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    entitlements = models.JSONField(default=dict)
    limits = models.JSONField(default=dict)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscription_plan_version"
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"],
                name="subscription_plan_code_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="subscription_plan_effective_range_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="DRAFT", published_at__isnull=True)
                | models.Q(
                    status__in=["PUBLISHED", "RETIRED"],
                    published_at__isnull=False,
                ),
                name="subscription_plan_publish_state_valid",
            ),
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
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {
                self.Status.PUBLISHED,
                self.Status.RETIRED,
            }:
                raise ValidationError("Published plan versions are immutable")
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
    ) -> tuple[int, dict[str, int]]:
        if self.status != self.Status.DRAFT:
            raise ValidationError("Published plan versions are immutable")
        return super().delete(using=using, keep_parents=keep_parents)


class CompanySubscription(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ACTIVE = "ACTIVE", "Active"
        GRACE = "GRACE", "Grace"
        SUSPENDED = "SUSPENDED", "Suspended"
        ENDED = "ENDED", "Ended"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.PROTECT,
        related_name="company_subscriptions",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    grace_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscription_company_subscription"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="subscription_company_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "starts_at"],
                name="sub_company_active_idx",
            )
        ]


class EntitlementOverride(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="entitlement_overrides",
    )
    entitlement_code = models.CharField(max_length=150)
    enabled = models.BooleanField()
    limit_value = models.PositiveBigIntegerField(null=True, blank=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    reason_code = models.CharField(max_length=100)
    set_by_public_id = models.UUIDField()

    class Meta:
        db_table = "subscription_entitlement_override"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entitlement_code", "effective_from"],
                name="subscription_override_effective_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="subscription_override_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entitlement_code", "effective_from"],
                name="sub_override_lookup_idx",
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
            raise ValidationError("Entitlement overrides are append-only")
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
        raise ValidationError("Entitlement overrides are append-only")
