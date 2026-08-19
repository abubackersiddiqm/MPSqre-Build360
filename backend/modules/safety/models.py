from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.fieldops.models import FieldStage
from modules.platform.models import TenantOwnedModel


class SafetyIncident(TenantOwnedModel):
    class Severity(models.TextChoices):
        NEAR_MISS = "near_miss", "Near miss"
        MINOR = "minor", "Minor"
        MAJOR = "major", "Major"
        CRITICAL = "critical", "Critical"
        FATAL = "fatal", "Fatal"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="safety_incidents"
    )
    stage = models.ForeignKey(FieldStage, on_delete=models.PROTECT, related_name="safety_incidents")
    incident_number = models.CharField(max_length=80)
    title = models.CharField(max_length=250)
    description = models.TextField()
    severity = models.CharField(max_length=30, choices=Severity.choices)
    occurred_at = models.DateTimeField()
    reported_at = models.DateTimeField()
    reported_by_membership_public_id = models.UUIDField()
    location = models.JSONField(default=dict)
    people_involved = models.JSONField(default=list)
    immediate_actions = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_actions = models.JSONField(default=list)
    evidence_file_public_ids = models.JSONField(default=list)
    operation_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "safety_incident"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "incident_number"], name="sft_incident_number_uq"
            ),
            models.UniqueConstraint(
                fields=["company", "operation_id"],
                condition=models.Q(operation_id__isnull=False),
                name="sft_incident_operation_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "stage", "occurred_at"],
                name="sft_incident_project_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Safety incident project cannot cross companies")
        if self.stage_id and (
            self.stage.company_id != self.company_id
            or self.stage.entity_type != FieldStage.EntityType.INCIDENT
        ):
            raise ValidationError("Safety incident requires an incident stage")


class SafetyObservation(TenantOwnedModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="safety_observations"
    )
    observation_number = models.CharField(max_length=80)
    observation_type = models.CharField(max_length=40)
    description = models.TextField()
    observed_at = models.DateTimeField()
    observed_by_membership_public_id = models.UUIDField()
    is_positive = models.BooleanField(default=False)
    action_required = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "safety_observation"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "observation_number"], name="sft_observation_number_uq"
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "project", "closed_at"], name="sft_observation_open_idx"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.project_id and self.project.company_id != self.company_id:
            raise ValidationError("Safety observation cannot cross companies")
