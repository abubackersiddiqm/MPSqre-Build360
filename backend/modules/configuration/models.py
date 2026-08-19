from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class ConfigurationDefinition(PublicIdModel, TimestampedModel):
    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True)
    schema = models.JSONField(default=dict)
    data_class = models.CharField(max_length=100, blank=True)
    is_secret = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "configuration_definition"


class ConfigurationVersion(PublicIdModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="configuration_versions",
    )
    definition = models.ForeignKey(
        ConfigurationDefinition,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    payload = models.JSONField(default=dict)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    created_by_public_id = models.UUIDField()
    published_at = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "configuration_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "definition", "version"],
                name="configuration_company_definition_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="configuration_effective_range_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="DRAFT", published_at__isnull=True)
                | models.Q(status__in=["PUBLISHED", "RETIRED"], published_at__isnull=False),
                name="configuration_publish_state_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "definition", "status", "effective_from"],
                name="cfg_active_lookup_idx",
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
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] in {
                self.Status.PUBLISHED,
                self.Status.RETIRED,
            }:
                raise ValidationError("Published configuration versions are immutable")
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
            raise ValidationError("Published configuration versions are immutable")
        return super().delete(using=using, keep_parents=keep_parents)
