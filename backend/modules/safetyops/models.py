from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def _clean_code(value: str) -> str:
    return value.strip().upper()


def _require_list(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValidationError({"configuration": f"{key} must be a list of non-empty codes"})


def _require_code(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"configuration": f"{key} must be a non-empty code"})


class SafetyPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="safety_policy_versions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField()
    status_code = models.CharField(max_length=80)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict)
    change_note = models.TextField(blank=True)
    created_by_membership_public_id = models.UUIDField(null=True, blank=True)
    published_by_membership_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "safetyops_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="safe_policy_code_ver_uniq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gt=F("effective_from")),
                name="safe_policy_range_valid",
            ),
            models.CheckConstraint(
                condition=Q(retired_at__isnull=True) | Q(published_at__isnull=False),
                name="safe_retire_after_publish",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "published_at", "retired_at"],
                name="safe_policy_active_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = _clean_code(self.code)
        self.status_code = _clean_code(self.status_code)
        if not isinstance(self.configuration, dict):
            raise ValidationError({"configuration": "Policy configuration must be an object"})
        for key in (
            "initial_observation_status",
            "initial_incident_status",
            "initial_permit_status",
            "initial_action_status",
            "initial_risk_status",
        ):
            _require_code(self.configuration, key)
        for key in (
            "open_observation_statuses",
            "open_incident_statuses",
            "active_permit_statuses",
            "open_action_statuses",
            "critical_severity_codes",
            "accepted_inspection_results",
        ):
            _require_list(self.configuration, key)
        for key in ("observation_transitions", "incident_transitions", "permit_transitions", "action_transitions"):
            value = self.configuration.get(key, [])
            if not isinstance(value, list):
                raise ValidationError({"configuration": f"{key} must be a list"})
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError({"effective_to": "Effective end must be after effective start"})
        if self.retired_at and not self.published_at:
            raise ValidationError({"retired_at": "A draft policy cannot be retired"})


class SafetyObservation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_observations")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="observations")
    observation_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    category_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    observed_at = models.DateTimeField()
    observed_by_membership_public_id = models.UUIDField()
    responsible_membership_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_note = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_observation"
        constraints = [
            models.UniqueConstraint(fields=["company", "observation_code"], name="safe_obs_code_uniq"),
            models.CheckConstraint(condition=Q(closed_at__isnull=True) | Q(closed_at__gte=F("observed_at")), name="safe_obs_close_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_at"], name="safe_obs_status_due_idx"),
            models.Index(fields=["company", "severity_code", "observed_at"], name="safe_obs_severity_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.observation_code = _clean_code(self.observation_code)
        self.category_code = _clean_code(self.category_code)
        self.severity_code = _clean_code(self.severity_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")


class SafetyIncident(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_incidents")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="incidents")
    incident_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    incident_type_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField()
    occurred_at = models.DateTimeField()
    reported_at = models.DateTimeField()
    reported_by_membership_public_id = models.UUIDField()
    affected_people_count = models.PositiveIntegerField(default=0)
    lost_time = models.BooleanField(default=False)
    regulator_reportable = models.BooleanField(default=False)
    immediate_action = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_incident"
        constraints = [
            models.UniqueConstraint(fields=["company", "incident_code"], name="safe_inc_code_uniq"),
            models.CheckConstraint(condition=Q(reported_at__gte=F("occurred_at")), name="safe_inc_report_valid"),
            models.CheckConstraint(condition=Q(closed_at__isnull=True) | Q(closed_at__gte=F("reported_at")), name="safe_inc_close_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "reported_at"], name="safe_inc_status_idx"),
            models.Index(fields=["company", "severity_code", "reported_at"], name="safe_inc_severity_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.incident_code = _clean_code(self.incident_code)
        self.incident_type_code = _clean_code(self.incident_type_code)
        self.severity_code = _clean_code(self.severity_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if self.reported_at and self.occurred_at and self.reported_at < self.occurred_at:
            raise ValidationError({"reported_at": "Reported time cannot precede occurrence"})


class PermitToWork(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_permits")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="permits")
    permit_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    permit_type_code = models.CharField(max_length=100)
    risk_level_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    work_summary = models.CharField(max_length=300)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    issuer_membership_public_id = models.UUIDField()
    receiver_membership_public_id = models.UUIDField()
    approved_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    conditions = models.JSONField(default=list, blank=True)
    isolation_points = models.JSONField(default=list, blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_permit"
        constraints = [
            models.UniqueConstraint(fields=["company", "permit_code"], name="safe_permit_code_uniq"),
            models.CheckConstraint(condition=Q(valid_until__gt=F("valid_from")), name="safe_permit_range_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "valid_until"], name="safe_permit_expiry_idx"),
            models.Index(fields=["company", "project_public_id", "location_public_id"], name="safe_permit_scope_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.permit_code = _clean_code(self.permit_code)
        self.permit_type_code = _clean_code(self.permit_type_code)
        self.risk_level_code = _clean_code(self.risk_level_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "Permit expiry must be after its start"})
        if not isinstance(self.conditions, list) or not isinstance(self.isolation_points, list):
            raise ValidationError("Permit conditions and isolation points must be lists")


class SafetyInspection(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_inspections")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="inspections")
    inspection_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    inspection_type_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    result_code = models.CharField(max_length=80, blank=True)
    scheduled_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    inspector_membership_public_id = models.UUIDField(null=True, blank=True)
    score_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    checklist_result = models.JSONField(default=dict)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_inspection"
        constraints = [
            models.UniqueConstraint(fields=["company", "inspection_code"], name="safe_insp_code_uniq"),
            models.CheckConstraint(condition=Q(completed_at__isnull=True) | Q(completed_at__gte=F("scheduled_at")), name="safe_insp_time_valid"),
            models.CheckConstraint(condition=Q(score_percent__isnull=True) | (Q(score_percent__gte=0) & Q(score_percent__lte=100)), name="safe_insp_score_valid"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "scheduled_at"], name="safe_insp_schedule_idx")]

    def clean(self) -> None:
        super().clean()
        self.inspection_code = _clean_code(self.inspection_code)
        self.inspection_type_code = _clean_code(self.inspection_type_code)
        self.status_code = _clean_code(self.status_code)
        self.result_code = _clean_code(self.result_code) if self.result_code else ""
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if not isinstance(self.checklist_result, dict):
            raise ValidationError({"checklist_result": "Checklist result must be an object"})


class ToolboxTalk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="toolbox_talks")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="toolbox_talks")
    talk_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    topic_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    delivered_at = models.DateTimeField()
    facilitator_membership_public_id = models.UUIDField()
    attendee_count = models.PositiveIntegerField(default=0)
    acknowledgement_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "safetyops_toolbox_talk"
        constraints = [
            models.UniqueConstraint(fields=["company", "talk_code"], name="safe_talk_code_uniq"),
            models.CheckConstraint(condition=Q(acknowledgement_count__lte=F("attendee_count")), name="safe_talk_ack_valid"),
        ]
        indexes = [models.Index(fields=["company", "delivered_at"], name="safe_talk_date_idx")]

    def clean(self) -> None:
        super().clean()
        self.talk_code = _clean_code(self.talk_code)
        self.topic_code = _clean_code(self.topic_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if self.acknowledgement_count > self.attendee_count:
            raise ValidationError({"acknowledgement_count": "Acknowledgements cannot exceed attendees"})


class CorrectiveAction(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_corrective_actions")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="corrective_actions")
    action_code = models.CharField(max_length=80)
    source_type_code = models.CharField(max_length=80)
    source_public_id = models.UUIDField(null=True, blank=True)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    category_code = models.CharField(max_length=100)
    priority_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by_membership_public_id = models.UUIDField(null=True, blank=True)
    closure_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_corrective_action"
        constraints = [
            models.UniqueConstraint(fields=["company", "action_code"], name="safe_action_code_uniq"),
            models.CheckConstraint(condition=Q(verified_at__isnull=True) | Q(completed_at__isnull=False), name="safe_action_verify_valid"),
        ]
        indexes = [
            models.Index(fields=["company", "status_code", "due_at"], name="safe_action_due_idx"),
            models.Index(fields=["company", "source_type_code", "source_public_id"], name="safe_action_source_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.action_code = _clean_code(self.action_code)
        self.source_type_code = _clean_code(self.source_type_code)
        self.category_code = _clean_code(self.category_code)
        self.priority_code = _clean_code(self.priority_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if self.verified_at and not self.completed_at:
            raise ValidationError({"verified_at": "Action must be completed before verification"})


class SafetyApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_approvals")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="approvals")
    entity_type_code = models.CharField(max_length=80)
    entity_public_id = models.UUIDField()
    step_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_by_membership_public_id = models.UUIDField()
    requested_from_membership_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    due_at = models.DateTimeField(null=True, blank=True)
    decided_by_membership_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "safetyops_approval"
        constraints = [
            models.UniqueConstraint(fields=["company", "entity_type_code", "entity_public_id", "step_code"], name="safe_approval_step_uniq"),
            models.CheckConstraint(condition=Q(decided_at__isnull=True) | Q(decided_by_membership_public_id__isnull=False), name="safe_approval_dec_valid"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "due_at"], name="safe_approval_due_idx")]

    def clean(self) -> None:
        super().clean()
        self.entity_type_code = _clean_code(self.entity_type_code)
        self.step_code = _clean_code(self.step_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
        if self.decided_at and not self.decided_by_membership_public_id:
            raise ValidationError({"decided_by_membership_public_id": "Decision actor is required"})


class SafetyRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="safety_risks")
    policy = models.ForeignKey(SafetyPolicyVersion, on_delete=models.PROTECT, related_name="risks")
    linked_entity_type_code = models.CharField(max_length=80)
    linked_entity_public_id = models.UUIDField(null=True, blank=True)
    risk_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.CharField(max_length=500)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_membership_public_id = models.UUIDField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        db_table = "safetyops_risk"
        constraints = [models.CheckConstraint(condition=Q(resolved_at__isnull=True) | Q(resolved_by_membership_public_id__isnull=False), name="safe_risk_resolve_valid")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="safe_risk_status_idx"),
            models.Index(fields=["company", "linked_entity_type_code", "linked_entity_public_id"], name="safe_risk_entity_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.linked_entity_type_code = _clean_code(self.linked_entity_type_code)
        self.risk_code = _clean_code(self.risk_code)
        self.severity_code = _clean_code(self.severity_code)
        self.status_code = _clean_code(self.status_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Safety policy cannot cross companies")
