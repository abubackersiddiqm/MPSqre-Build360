from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import TenantOwnedModel
from modules.projects.models import DeliveryStage, Project


class Estimate(TenantOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="estimates")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    currency = models.CharField(max_length=3)
    created_by_public_id = models.UUIDField()
    version = models.PositiveBigIntegerField(default=1)
    active_version_number = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "estimation_estimate"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "project", "code"],
                name="est_project_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "archived_at"],
                name="est_project_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Estimate project cannot cross companies")


class EstimateVersion(TenantOwnedModel):
    estimate = models.ForeignKey(Estimate, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    stage = models.ForeignKey(
        DeliveryStage,
        on_delete=models.PROTECT,
        related_name="estimate_versions",
    )
    notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    tax_total = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    grand_total = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    created_by_public_id = models.UUIDField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    baselined_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "estimation_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "estimate", "version_number"],
                name="est_version_number_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0)
                & models.Q(tax_total__gte=0)
                & models.Q(grand_total__gte=0),
                name="est_totals_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "estimate", "stage", "version_number"],
                name="est_version_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.estimate_id and self.estimate.company_id != self.company_id:
            raise ValidationError("Estimate version cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != DeliveryStage.EntityType.ESTIMATE_VERSION
        ):
            raise ValidationError("Estimate version requires an estimate stage")


class BoqSection(TenantOwnedModel):
    estimate_version = models.ForeignKey(
        EstimateVersion,
        on_delete=models.PROTECT,
        related_name="sections",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "estimation_boq_section"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "estimate_version", "code"],
                name="est_section_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "estimate_version", "sort_order"],
                name="est_section_order_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.estimate_version_id and self.estimate_version.company_id != self.company_id:
            raise ValidationError("BOQ section cannot cross companies")


class BoqItem(TenantOwnedModel):
    estimate_version = models.ForeignKey(
        EstimateVersion,
        on_delete=models.PROTECT,
        related_name="items",
    )
    section = models.ForeignKey(
        BoqSection,
        on_delete=models.PROTECT,
        related_name="items",
        null=True,
        blank=True,
    )
    item_code = models.CharField(max_length=80)
    description = models.TextField()
    unit_code = models.CharField(max_length=40)
    quantity = models.DecimalField(max_digits=19, decimal_places=4)
    rate = models.DecimalField(max_digits=19, decimal_places=4)
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    tax_rate_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"))
    tax_amount = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    total_amount = models.DecimalField(max_digits=19, decimal_places=4)
    sort_order = models.PositiveIntegerField(default=100)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "estimation_boq_item"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "estimate_version", "item_code"],
                name="est_item_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0)
                & models.Q(rate__gte=0)
                & models.Q(amount__gte=0)
                & models.Q(tax_rate_percent__gte=0)
                & models.Q(tax_rate_percent__lte=100)
                & models.Q(total_amount__gte=0),
                name="est_item_values_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "estimate_version", "section", "sort_order"],
                name="est_item_order_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.estimate_version_id and self.estimate_version.company_id != self.company_id:
            raise ValidationError("BOQ item cannot cross companies")
        if self.section_id and (
            self.section.company_id != self.company_id
            or self.section.estimate_version_id != self.estimate_version_id
        ):
            raise ValidationError("BOQ section must belong to the same estimate version")


class EstimateBaseline(TenantOwnedModel):
    estimate = models.ForeignKey(Estimate, on_delete=models.PROTECT, related_name="baselines")
    estimate_version = models.OneToOneField(
        EstimateVersion,
        on_delete=models.PROTECT,
        related_name="baseline_record",
    )
    snapshot = models.JSONField(default=dict)
    created_by_public_id = models.UUIDField()

    class Meta:
        db_table = "estimation_baseline"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "estimate", "estimate_version"],
                name="est_baseline_version_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.estimate_id and self.estimate.company_id != self.company_id:
            raise ValidationError("Estimate baseline cannot cross companies")
        if self.estimate_version_id and (
            self.estimate_version.company_id != self.company_id
            or self.estimate_version.estimate_id != self.estimate_id
        ):
            raise ValidationError("Baseline version must belong to the same estimate")
