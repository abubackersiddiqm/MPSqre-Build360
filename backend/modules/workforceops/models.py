from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def _validate_code_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError({"configuration": f"{field_name} must be a list of codes"})


class WorkforcePolicyVersion(PublicIdModel, TimestampedModel):
    """Versioned, tenant-owned workforce planning control policy.

    Workflow statuses, approvals, capacity rules, credential requirements and
    adapter references live in ``configuration``. No role, trade, project,
    jurisdiction or certification rule is hardcoded by this bounded context.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_policy_versions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=80)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    configuration = models.JSONField(default=dict)
    change_note = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "workforce_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="wkfpol_company_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="wkfpol_effective_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(retired_at__isnull=True)
                | models.Q(published_at__isnull=False),
                name="wkfpol_retired_publish_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "status_code"],
                name="wkfpol_company_status_idx",
            ),
            models.Index(
                fields=["company", "effective_from", "effective_to"],
                name="wkfpol_effective_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError("Policy effective_to must be after effective_from")
        configuration = self.configuration or {}
        if not isinstance(configuration, dict):
            raise ValidationError({"configuration": "Configuration must be an object"})
        initial_status = configuration.get("initial_plan_status")
        if not isinstance(initial_status, str) or not initial_status.strip():
            raise ValidationError(
                {"configuration": "initial_plan_status must be a non-empty string"}
            )
        _validate_code_list(configuration.get("immutable_statuses", []), "immutable_statuses")
        transitions = configuration.get("transitions")
        if not isinstance(transitions, list):
            raise ValidationError({"configuration": "transitions must be a list"})
        transition_pairs: set[tuple[str, str]] = set()
        for index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise ValidationError(
                    {"configuration": f"Transition {index + 1} must be an object"}
                )
            for key in ("from", "to", "permission"):
                if not isinstance(transition.get(key), str) or not transition[key].strip():
                    raise ValidationError(
                        {"configuration": f"Transition {index + 1} requires {key}"}
                    )
            source = transition["from"].strip()
            target = transition["to"].strip()
            if source == target:
                raise ValidationError(
                    {"configuration": f"Transition {index + 1} cannot be a self-loop"}
                )
            if (source, target) in transition_pairs:
                raise ValidationError(
                    {"configuration": f"Transition {source} to {target} is duplicated"}
                )
            transition_pairs.add((source, target))
            approvals = transition.get("required_approvals", [])
            if not isinstance(approvals, list):
                raise ValidationError(
                    {"configuration": "required_approvals must be a list"}
                )
            for requirement in approvals:
                if not isinstance(requirement, dict):
                    raise ValidationError(
                        {"configuration": "Approval requirements must be objects"}
                    )
                step_code = requirement.get("step_code")
                accepted = requirement.get("accepted_statuses")
                if (
                    not isinstance(step_code, str)
                    or not step_code.strip()
                    or not isinstance(accepted, list)
                    or not accepted
                    or any(not isinstance(item, str) or not item.strip() for item in accepted)
                ):
                    raise ValidationError(
                        {"configuration": "Approval requirement is incomplete"}
                    )
        enforcement = configuration.get("credential_enforcement")
        if not isinstance(enforcement, str) or enforcement.strip().upper() not in {
            "BLOCK",
            "RISK",
            "OFF",
        }:
            raise ValidationError(
                {
                    "configuration": (
                        "credential_enforcement must be BLOCK, RISK or OFF"
                    )
                }
            )
        accepted_statuses = configuration.get("accepted_verification_statuses")
        _validate_code_list(
            accepted_statuses,
            "accepted_verification_statuses",
        )
        if enforcement.strip().upper() == "RISK":
            for key in (
                "credential_gap_risk_code",
                "credential_gap_severity",
                "open_risk_status",
            ):
                value = configuration.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValidationError(
                        {"configuration": f"{key} is required for RISK enforcement"}
                    )
        filled_status = configuration.get("filled_demand_status", "")
        if not isinstance(filled_status, str):
            raise ValidationError(
                {"configuration": "filled_demand_status must be a code"}
            )
        decisions = configuration.get("approval_decisions", {})
        if not isinstance(decisions, dict) or any(
            not isinstance(code, str)
            or not code.strip()
            or not isinstance(status, str)
            or not status.strip()
            for code, status in decisions.items()
        ):
            raise ValidationError(
                {"configuration": "approval_decisions must map decision to status"}
            )


class SkillDefinition(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_skill_definitions",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    category_code = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    proficiency_scale = models.JSONField(default=list)
    is_certification = models.BooleanField(default=False)
    default_validity_days = models.PositiveIntegerField(null=True, blank=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict)

    class Meta:
        db_table = "workforce_skill_definition"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="wskill_company_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="wskill_effective_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "is_active"],
                name="wskill_lookup_idx",
            ),
            models.Index(
                fields=["company", "category_code", "is_active"],
                name="wskill_category_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError("Skill effective_to must be after effective_from")
        if not isinstance(self.proficiency_scale, list) or any(
            not isinstance(item, str) or not item.strip()
            for item in self.proficiency_scale
        ):
            raise ValidationError(
                {"proficiency_scale": "Proficiency scale must be a list of codes"}
            )
        normalized = [item.strip().casefold() for item in self.proficiency_scale]
        if len(normalized) != len(set(normalized)):
            raise ValidationError(
                {"proficiency_scale": "Proficiency codes must be unique"}
            )
        if not isinstance(self.configuration or {}, dict):
            raise ValidationError({"configuration": "Configuration must be an object"})


class WorkforcePlan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_plans",
    )
    policy = models.ForeignKey(
        WorkforcePolicyVersion,
        on_delete=models.PROTECT,
        related_name="plans",
    )
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status_code = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    owner_membership_public_id = models.UUIDField()
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_plan"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="wplan_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="wplan_date_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "created_at"],
                name="wplan_company_status_idx",
            ),
            models.Index(
                fields=["company", "starts_on", "ends_on"],
                name="wplan_company_dates_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Workforce plan policy cannot cross companies")
        if self.ends_on < self.starts_on:
            raise ValidationError("Plan ends_on cannot be before starts_on")
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class WorkforceDemand(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_demands",
    )
    plan = models.ForeignKey(
        WorkforcePlan,
        on_delete=models.PROTECT,
        related_name="demands",
    )
    demand_code = models.CharField(max_length=100)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    cost_center_code = models.CharField(max_length=100, blank=True)
    role_code = models.CharField(max_length=100)
    employment_type_code = models.CharField(max_length=80, blank=True)
    priority_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    quantity_required = models.PositiveIntegerField()
    quantity_filled = models.PositiveIntegerField(default=0)
    starts_on = models.DateField()
    ends_on = models.DateField()
    estimated_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    currency = models.CharField(max_length=3)
    skill_requirements = models.JSONField(default=list)
    configuration = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workforce_demand"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "demand_code"],
                name="wdemand_plan_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_required__gte=1)
                & models.Q(quantity_filled__lte=models.F("quantity_required")),
                name="wdemand_qty_valid_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="wdemand_date_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_cost__gte=0),
                name="wdemand_cost_nonneg_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "priority_code"],
                name="wdemand_status_prio_idx",
            ),
            models.Index(
                fields=["company", "project_public_id", "starts_on"],
                name="wdemand_project_dates_idx",
            ),
            models.Index(
                fields=["plan", "status_code"],
                name="wdemand_plan_status_idx",
            ),
        ]

    @property
    def open_quantity(self) -> int:
        return max(self.quantity_required - self.quantity_filled, 0)

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.company_id and self.plan.company_id != self.company_id:
            raise ValidationError("Workforce demand cannot cross companies")
        if self.quantity_required < 1:
            raise ValidationError({"quantity_required": "Quantity must be at least one"})
        if self.quantity_filled > self.quantity_required:
            raise ValidationError({"quantity_filled": "Filled quantity exceeds demand"})
        if self.ends_on < self.starts_on:
            raise ValidationError("Demand ends_on cannot be before starts_on")
        if self.estimated_cost < 0:
            raise ValidationError({"estimated_cost": "Estimated cost cannot be negative"})
        if not isinstance(self.skill_requirements, list):
            raise ValidationError(
                {"skill_requirements": "Skill requirements must be a list"}
            )
        seen: set[str] = set()
        for index, requirement in enumerate(self.skill_requirements):
            if not isinstance(requirement, dict):
                raise ValidationError(
                    {"skill_requirements": f"Requirement {index + 1} must be an object"}
                )
            code = requirement.get("skill_code")
            if not isinstance(code, str) or not code.strip():
                raise ValidationError(
                    {"skill_requirements": f"Requirement {index + 1} needs skill_code"}
                )
            normalized = code.strip().casefold()
            if normalized in seen:
                raise ValidationError(
                    {"skill_requirements": f"Skill {code} is duplicated"}
                )
            seen.add(normalized)
        if not isinstance(self.configuration or {}, dict):
            raise ValidationError({"configuration": "Configuration must be an object"})


class WorkforceAssignment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_assignments",
    )
    demand = models.ForeignKey(
        WorkforceDemand,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    employee_public_id = models.UUIDField()
    assignment_status_code = models.CharField(max_length=80)
    allocation_percent = models.DecimalField(max_digits=5, decimal_places=2)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    source_reference = models.CharField(max_length=150, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["demand", "employee_public_id", "starts_on"],
                name="wassign_demand_emp_start_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(allocation_percent__gte=0.01)
                & models.Q(allocation_percent__lte=100),
                name="wassign_alloc_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="wassign_date_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employee_public_id", "assignment_status_code"],
                name="wassign_employee_status_idx",
            ),
            models.Index(
                fields=["demand", "assignment_status_code"],
                name="wassign_demand_status_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.demand_id and self.company_id and self.demand.company_id != self.company_id:
            raise ValidationError("Workforce assignment cannot cross companies")
        if self.allocation_percent <= 0 or self.allocation_percent > 100:
            raise ValidationError(
                {"allocation_percent": "Allocation must be greater than zero and at most 100"}
            )
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError("Assignment ends_on cannot be before starts_on")
        if self.starts_on < self.demand.starts_on or self.starts_on > self.demand.ends_on:
            raise ValidationError(
                {"starts_on": "Assignment start must fall inside the demand window"}
            )
        if self.ends_on and self.ends_on > self.demand.ends_on:
            raise ValidationError(
                {"ends_on": "Assignment end cannot exceed the demand window"}
            )
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EmployeeSkillCredential(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_credentials",
    )
    employee_public_id = models.UUIDField()
    skill = models.ForeignKey(
        SkillDefinition,
        on_delete=models.PROTECT,
        related_name="employee_credentials",
    )
    proficiency_code = models.CharField(max_length=80)
    credential_reference = models.CharField(max_length=150, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    verification_status_code = models.CharField(max_length=80)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    evidence_object_key = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "workforce_employee_credential"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_public_id", "skill", "issued_on"],
                name="wcred_emp_skill_issue_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(issued_on__isnull=True)
                | models.Q(expires_on__isnull=True)
                | models.Q(expires_on__gte=models.F("issued_on")),
                name="wcred_date_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "expires_on", "verification_status_code"],
                name="wcred_expiry_status_idx",
            ),
            models.Index(
                fields=["company", "employee_public_id"],
                name="wcred_employee_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.skill_id and self.company_id and self.skill.company_id != self.company_id:
            raise ValidationError("Credential skill cannot cross companies")
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValidationError("Credential expires_on cannot be before issued_on")
        if self.skill_id and self.skill.proficiency_scale:
            allowed = {item.casefold() for item in self.skill.proficiency_scale}
            if self.proficiency_code.casefold() not in allowed:
                raise ValidationError(
                    {"proficiency_code": "Proficiency is not in the configured scale"}
                )
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class WorkforceApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_approvals",
    )
    plan = models.ForeignKey(
        WorkforcePlan,
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    step_code = models.CharField(max_length=100)
    status_code = models.CharField(max_length=80)
    requested_from_membership_public_id = models.UUIDField()
    requested_by_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    due_at = models.DateTimeField(null=True, blank=True)
    decided_by_public_id = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_code = models.CharField(max_length=80, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workforce_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "step_code"],
                name="wapproval_plan_step_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "requested_at"],
                name="wapproval_status_idx",
            ),
            models.Index(
                fields=["company", "due_at", "decided_at"],
                name="wapproval_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.company_id and self.plan.company_id != self.company_id:
            raise ValidationError("Workforce approval cannot cross companies")
        if self.decided_at and not self.decision_code:
            raise ValidationError({"decision_code": "Decision code is required"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class WorkforceRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_risks",
    )
    plan = models.ForeignKey(
        WorkforcePlan,
        on_delete=models.PROTECT,
        related_name="risks",
        null=True,
        blank=True,
    )
    demand = models.ForeignKey(
        WorkforceDemand,
        on_delete=models.PROTECT,
        related_name="risks",
        null=True,
        blank=True,
    )
    employee_public_id = models.UUIDField(null=True, blank=True)
    risk_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.CharField(max_length=1000)
    due_at = models.DateTimeField(null=True, blank=True)
    assigned_to_membership_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolution_note = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "workforce_risk"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(plan__isnull=False)
                | models.Q(demand__isnull=False)
                | models.Q(employee_public_id__isnull=False),
                name="wrisk_subject_present_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code"],
                name="wrisk_status_severity_idx",
            ),
            models.Index(
                fields=["company", "due_at", "resolved_at"],
                name="wrisk_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not (self.plan_id or self.demand_id or self.employee_public_id):
            raise ValidationError("A workforce risk must identify a subject")
        if self.plan_id and self.company_id and self.plan.company_id != self.company_id:
            raise ValidationError("Workforce risk plan cannot cross companies")
        if self.demand_id and self.company_id and self.demand.company_id != self.company_id:
            raise ValidationError("Workforce risk demand cannot cross companies")
        if self.plan_id and self.demand_id and self.demand.plan_id != self.plan_id:
            raise ValidationError("Risk demand must belong to the selected plan")
        if self.resolved_at and not self.resolution_note.strip():
            raise ValidationError({"resolution_note": "Resolution note is required"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class WorkforceExportBatch(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="workforce_export_batches",
    )
    plan = models.ForeignKey(
        WorkforcePlan,
        on_delete=models.PROTECT,
        related_name="export_batches",
        null=True,
        blank=True,
    )
    export_type_code = models.CharField(max_length=100)
    provider_code = models.CharField(max_length=100, blank=True)
    status_code = models.CharField(max_length=80)
    object_key = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    requested_by_public_id = models.UUIDField()
    requested_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "workforce_export_batch"
        indexes = [
            models.Index(
                fields=["company", "status_code", "created_at"],
                name="wexport_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.plan_id and self.company_id and self.plan.company_id != self.company_id:
            raise ValidationError("Workforce export plan cannot cross companies")
        if self.checksum_sha256 and len(self.checksum_sha256) != 64:
            raise ValidationError({"checksum_sha256": "Checksum must be SHA-256"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})
