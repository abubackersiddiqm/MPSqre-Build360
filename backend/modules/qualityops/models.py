from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def _code(value: str) -> str:
    return value.strip().upper()


def _require_code(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({"configuration": f"{key} must be a non-empty code"})


def _require_codes(configuration: dict[str, Any], key: str) -> None:
    value = configuration.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValidationError(
            {"configuration": f"{key} must be a list of non-empty codes"}
        )


class QualityPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_policy_versions"
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
        db_table = "qualityops_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"], name="qops_pol_code_ver_uq"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=F("effective_from")),
                name="qops_pol_range_ck",
            ),
            models.CheckConstraint(
                condition=Q(retired_at__isnull=True)
                | Q(published_at__isnull=False),
                name="qops_pol_retire_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "published_at", "retired_at"],
                name="qops_pol_active_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = _code(self.code)
        self.status_code = _code(self.status_code)
        if not isinstance(self.configuration, dict):
            raise ValidationError({"configuration": "Policy configuration must be an object"})
        for key in (
            "initial_itp_status",
            "initial_request_status",
            "initial_inspection_status",
            "initial_ncr_status",
            "initial_action_status",
            "initial_risk_status",
        ):
            _require_code(self.configuration, key)
        for key in (
            "active_itp_statuses",
            "open_request_statuses",
            "open_ncr_statuses",
            "open_action_statuses",
            "critical_severity_codes",
            "accepted_inspection_results",
            "accepted_test_results",
        ):
            _require_codes(self.configuration, key)
        for key in (
            "itp_transitions",
            "request_transitions",
            "ncr_transitions",
            "action_transitions",
        ):
            if not isinstance(self.configuration.get(key, []), list):
                raise ValidationError({"configuration": f"{key} must be a list"})
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError({"effective_to": "Effective end must follow effective start"})
        if self.retired_at and not self.published_at:
            raise ValidationError({"retired_at": "A draft policy cannot be retired"})


class InspectionTestPlan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_itps"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="itps"
    )
    itp_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    discipline_code = models.CharField(max_length=100)
    work_package_code = models.CharField(max_length=120)
    revision = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    hold_points = models.JSONField(default=list, blank=True)
    witness_points = models.JSONField(default=list, blank=True)
    acceptance_criteria = models.JSONField(default=dict, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_membership_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_itp"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "itp_code", "revision"], name="qops_itp_code_rev_uq"
            ),
            models.CheckConstraint(condition=Q(revision__gte=1), name="qops_itp_rev_ck"),
            models.CheckConstraint(
                condition=Q(approved_at__isnull=True)
                | Q(approved_by_membership_public_id__isnull=False),
                name="qops_itp_approve_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "discipline_code"],
                name="qops_itp_status_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("itp_code", "discipline_code", "work_package_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if not isinstance(self.hold_points, list) or not isinstance(self.witness_points, list):
            raise ValidationError("Hold points and witness points must be lists")
        if not isinstance(self.acceptance_criteria, dict):
            raise ValidationError({"acceptance_criteria": "Acceptance criteria must be an object"})


class QualityInspectionRequest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_inspection_requests"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="inspection_requests"
    )
    itp = models.ForeignKey(
        InspectionTestPlan,
        on_delete=models.PROTECT,
        related_name="inspection_requests",
        null=True,
        blank=True,
    )
    request_code = models.CharField(max_length=80)
    request_type_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    activity_code = models.CharField(max_length=120)
    lot_or_batch_code = models.CharField(max_length=120, blank=True)
    supplier_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=80)
    requested_for = models.DateTimeField()
    requested_by_membership_public_id = models.UUIDField()
    assigned_inspector_membership_public_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_inspection_request"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "request_code"], name="qops_req_code_uq"
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "requested_for"],
                name="qops_req_status_ix",
            ),
            models.Index(
                fields=["company", "request_type_code", "project_public_id"],
                name="qops_req_type_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("request_code", "request_type_code", "activity_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.lot_or_batch_code:
            self.lot_or_batch_code = _code(self.lot_or_batch_code)
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if self.itp_id and self.itp.company_id != self.company_id:
            raise ValidationError("Inspection test plan cannot cross companies")
        if self.itp_id and self.itp.policy_id != self.policy_id:
            raise ValidationError("Inspection request and ITP must use the same policy")


class QualityInspection(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_inspections"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="inspections"
    )
    request = models.ForeignKey(
        QualityInspectionRequest,
        on_delete=models.PROTECT,
        related_name="inspections",
        null=True,
        blank=True,
    )
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
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )
    sample_size = models.PositiveIntegerField(default=0)
    accepted_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    checklist_result = models.JSONField(default=dict)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_inspection"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "inspection_code"], name="qops_insp_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(completed_at__isnull=True)
                | Q(completed_at__gte=F("scheduled_at")),
                name="qops_insp_time_ck",
            ),
            models.CheckConstraint(
                condition=Q(score_percent__isnull=True)
                | (Q(score_percent__gte=0) & Q(score_percent__lte=100)),
                name="qops_insp_score_ck",
            ),
            models.CheckConstraint(
                condition=Q(accepted_quantity__lte=F("sample_size")),
                name="qops_insp_accept_ck",
            ),
            models.CheckConstraint(
                condition=Q(rejected_quantity__lte=F("sample_size")),
                name="qops_insp_reject_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "scheduled_at"],
                name="qops_insp_sched_ix",
            ),
            models.Index(
                fields=["company", "result_code", "completed_at"],
                name="qops_insp_result_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("inspection_code", "inspection_type_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        self.result_code = _code(self.result_code) if self.result_code else ""
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if self.request_id and self.request.company_id != self.company_id:
            raise ValidationError("Inspection request cannot cross companies")
        if self.request_id and self.request.policy_id != self.policy_id:
            raise ValidationError("Inspection and request must use the same policy")
        if self.accepted_quantity + self.rejected_quantity > self.sample_size:
            raise ValidationError("Accepted and rejected quantities cannot exceed sample size")
        if not isinstance(self.checklist_result, dict):
            raise ValidationError({"checklist_result": "Checklist result must be an object"})


class QualityTestResult(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_test_results"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="test_results"
    )
    inspection = models.ForeignKey(
        QualityInspection,
        on_delete=models.PROTECT,
        related_name="test_results",
        null=True,
        blank=True,
    )
    test_code = models.CharField(max_length=80)
    test_type_code = models.CharField(max_length=100)
    specimen_code = models.CharField(max_length=120, blank=True)
    laboratory_reference = models.CharField(max_length=160, blank=True)
    result_code = models.CharField(max_length=80)
    measured_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit_code = models.CharField(max_length=40, blank=True)
    specification_min = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    specification_max = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    tested_at = models.DateTimeField()
    tested_by_membership_public_id = models.UUIDField(null=True, blank=True)
    certificate_reference = models.CharField(max_length=500, blank=True)
    remarks = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_test_result"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "test_code"], name="qops_test_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(specification_min__isnull=True)
                | Q(specification_max__isnull=True)
                | Q(specification_max__gte=F("specification_min")),
                name="qops_test_spec_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "result_code", "tested_at"],
                name="qops_test_result_ix",
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("test_code", "test_type_code", "result_code"):
            setattr(self, field, _code(getattr(self, field)))
        for field in ("specimen_code", "unit_code"):
            value = getattr(self, field)
            setattr(self, field, _code(value) if value else "")
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if self.inspection_id and self.inspection.company_id != self.company_id:
            raise ValidationError("Inspection cannot cross companies")
        if self.inspection_id and self.inspection.policy_id != self.policy_id:
            raise ValidationError("Test result and inspection must use the same policy")
        if (
            self.specification_min is not None
            and self.specification_max is not None
            and self.specification_max < self.specification_min
        ):
            raise ValidationError("Maximum specification cannot be below minimum")


class NonConformanceReport(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_ncrs"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="ncrs"
    )
    ncr_code = models.CharField(max_length=80)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    source_type_code = models.CharField(max_length=80)
    source_public_id = models.UUIDField(null=True, blank=True)
    category_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    title = models.CharField(max_length=240)
    description = models.TextField()
    detected_at = models.DateTimeField()
    detected_by_membership_public_id = models.UUIDField()
    responsible_membership_public_id = models.UUIDField(null=True, blank=True)
    root_cause = models.TextField(blank=True)
    disposition_code = models.CharField(max_length=100, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_note = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_ncr"
        constraints = [
            models.UniqueConstraint(fields=["company", "ncr_code"], name="qops_ncr_code_uq"),
            models.CheckConstraint(
                condition=Q(closed_at__isnull=True) | Q(closed_at__gte=F("detected_at")),
                name="qops_ncr_close_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"], name="qops_ncr_status_ix"
            ),
            models.Index(
                fields=["company", "severity_code", "detected_at"],
                name="qops_ncr_severity_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "ncr_code",
            "source_type_code",
            "category_code",
            "severity_code",
            "status_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        self.disposition_code = _code(self.disposition_code) if self.disposition_code else ""
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")


class QualityCorrectiveAction(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_corrective_actions"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="corrective_actions"
    )
    action_code = models.CharField(max_length=80)
    source_type_code = models.CharField(max_length=80)
    source_public_id = models.UUIDField(null=True, blank=True)
    project_public_id = models.UUIDField(null=True, blank=True)
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
        db_table = "qualityops_corrective_action"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "action_code"], name="qops_act_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(verified_at__isnull=True) | Q(completed_at__isnull=False),
                name="qops_act_verify_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"], name="qops_act_due_ix"
            ),
            models.Index(
                fields=["company", "source_type_code", "source_public_id"],
                name="qops_act_source_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in (
            "action_code",
            "source_type_code",
            "category_code",
            "priority_code",
            "status_code",
        ):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if self.verified_at and not self.completed_at:
            raise ValidationError({"verified_at": "Action must be completed before verification"})


class QualityApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_approvals"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="approvals"
    )
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
        db_table = "qualityops_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type_code", "entity_public_id", "step_code"],
                name="qops_appr_step_uq",
            ),
            models.CheckConstraint(
                condition=Q(decided_at__isnull=True)
                | Q(decided_by_membership_public_id__isnull=False),
                name="qops_appr_decide_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "due_at"], name="qops_appr_due_ix"
            )
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("entity_type_code", "step_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
        if self.decided_at and not self.decided_by_membership_public_id:
            raise ValidationError({"decided_by_membership_public_id": "Decision actor is required"})


class QualityRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="quality_risks"
    )
    policy = models.ForeignKey(
        QualityPolicyVersion, on_delete=models.PROTECT, related_name="risks"
    )
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
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "qualityops_risk"
        constraints = [
            models.CheckConstraint(
                condition=Q(resolved_at__isnull=True)
                | Q(resolved_by_membership_public_id__isnull=False),
                name="qops_risk_resolve_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code"],
                name="qops_risk_status_ix",
            ),
            models.Index(
                fields=["company", "linked_entity_type_code", "linked_entity_public_id"],
                name="qops_risk_entity_ix",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        for field in ("linked_entity_type_code", "risk_code", "severity_code", "status_code"):
            setattr(self, field, _code(getattr(self, field)))
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Quality policy cannot cross companies")
