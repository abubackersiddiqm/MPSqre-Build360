from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.fieldops.models import FieldStage
from modules.platform.models import TenantOwnedModel


class InspectionTemplate(TenantOwnedModel):
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    discipline_code = models.CharField(max_length=80)
    version_number = models.PositiveIntegerField(default=1)
    checklist = models.JSONField(default=list)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "quality_inspection_template"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version_number"], name="qlt_template_version_uq"
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "discipline_code", "is_published"],
                name="qlt_template_active_idx",
            )
        ]


class Inspection(TenantOwnedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="inspections"
    )
    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.PROTECT, related_name="inspections"
    )
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="inspections")
    inspection_number = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    location = models.JSONField(default=dict)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    inspected_at = models.DateTimeField(null=True, blank=True)
    inspector_membership_public_id = models.UUIDField()
    checklist_result = models.JSONField(default=list)
    overall_result = models.CharField(max_length=30, blank=True)
    evidence_file_public_ids = models.JSONField(default=list)
    operation_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "quality_inspection"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "inspection_number"], name="qlt_inspection_number_uq"
            ),
            models.UniqueConstraint(
                fields=["company", "operation_id"],
                condition=models.Q(operation_id__isnull=False),
                name="qlt_inspection_operation_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project", "stage"], name="qlt_inspection_project_idx")
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Inspection project cannot cross companies")
        if self.template_id and self.template.company_id != self.company_id:
            raise ValidationError("Inspection template cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.INSPECTION
        ):
            raise ValidationError("Inspection requires an inspection stage")


class NonConformanceReport(TenantOwnedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="ncrs")
    inspection = models.ForeignKey(
        Inspection, on_delete=models.PROTECT, related_name="ncrs", null=True, blank=True
    )
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="ncrs")
    ncr_number = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    description = models.TextField()
    severity = models.CharField(max_length=30)
    responsible_membership_public_id = models.UUIDField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "quality_non_conformance"
        constraints = [
            models.UniqueConstraint(fields=["company", "ncr_number"], name="qlt_ncr_number_uq")
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "stage", "due_date"], name="qlt_ncr_project_idx"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("NCR project cannot cross companies")
        if self.inspection_id and (
            self.inspection.company_id != self.company_id
            or self.inspection.project_id != self.project_id
        ):
            raise ValidationError("NCR inspection must belong to the same project")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.NCR
        ):
            raise ValidationError("NCR requires an NCR stage")
