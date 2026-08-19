from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def _object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError({field_name: f"{field_name} must be an object"})
    return value


def _code_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError({"configuration": f"{field_name} must be a list of codes"})
    normalized = [item.strip() for item in value]
    if len({item.casefold() for item in normalized}) != len(normalized):
        raise ValidationError({"configuration": f"{field_name} contains duplicate codes"})
    return normalized


class EquipmentPolicyVersion(PublicIdModel, TimestampedModel):
    """Versioned tenant-owned plant, equipment and fleet control policy."""

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_policy_versions",
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
        db_table = "equipmentops_policy_version"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code", "version"],
                name="eqpol_company_code_ver_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="eqpol_effective_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(retired_at__isnull=True)
                | models.Q(published_at__isnull=False),
                name="eqpol_retired_publish_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "code", "status_code"],
                name="eqpol_company_status_idx",
            ),
            models.Index(
                fields=["company", "effective_from", "effective_to"],
                name="eqpol_effective_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError("Policy effective_to must be after effective_from")
        configuration = _object(self.configuration or {}, "configuration")
        for key in (
            "initial_asset_status",
            "initial_deployment_status",
            "initial_work_order_status",
            "open_risk_status",
        ):
            value = configuration.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError({"configuration": f"{key} must be a code"})
        _code_list(configuration.get("immutable_asset_statuses", []), "immutable_asset_statuses")
        _code_list(configuration.get("active_deployment_statuses", []), "active_deployment_statuses")
        _code_list(configuration.get("open_work_order_statuses", []), "open_work_order_statuses")
        _code_list(configuration.get("accepted_inspection_results", []), "accepted_inspection_results")
        meter_action = configuration.get("meter_regression_action")
        if not isinstance(meter_action, str) or meter_action.upper() not in {
            "BLOCK",
            "RISK",
            "OFF",
        }:
            raise ValidationError(
                {"configuration": "meter_regression_action must be BLOCK, RISK or OFF"}
            )
        if meter_action.upper() == "RISK":
            for key in ("meter_regression_risk_code", "meter_regression_severity"):
                value = configuration.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValidationError({"configuration": f"{key} is required"})
        transitions = configuration.get("work_order_transitions", [])
        if not isinstance(transitions, list):
            raise ValidationError({"configuration": "work_order_transitions must be a list"})
        seen: set[tuple[str, str]] = set()
        for index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise ValidationError(
                    {"configuration": f"Transition {index + 1} must be an object"}
                )
            for key in ("from", "to", "permission"):
                value = transition.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ValidationError(
                        {"configuration": f"Transition {index + 1} requires {key}"}
                    )
            pair = (transition["from"].strip(), transition["to"].strip())
            if pair[0] == pair[1] or pair in seen:
                raise ValidationError(
                    {"configuration": f"Transition {pair[0]} to {pair[1]} is invalid"}
                )
            seen.add(pair)
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
                if not isinstance(requirement.get("step_code"), str):
                    raise ValidationError(
                        {"configuration": "Approval requirement needs step_code"}
                    )
                _code_list(
                    requirement.get("accepted_statuses", []),
                    "accepted_statuses",
                )
        decisions = configuration.get("approval_decisions", {})
        if not isinstance(decisions, dict) or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in decisions.items()
        ):
            raise ValidationError(
                {"configuration": "approval_decisions must map decision to status"}
            )


class EquipmentAsset(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_assets",
    )
    policy = models.ForeignKey(
        EquipmentPolicyVersion,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    asset_code = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    category_code = models.CharField(max_length=80)
    asset_type_code = models.CharField(max_length=80)
    ownership_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    manufacturer = models.CharField(max_length=150, blank=True)
    model_reference = models.CharField(max_length=150, blank=True)
    serial_number = models.CharField(max_length=150, blank=True)
    registration_number = models.CharField(max_length=150, blank=True)
    commissioned_on = models.DateField(null=True, blank=True)
    decommissioned_on = models.DateField(null=True, blank=True)
    home_location_public_id = models.UUIDField(null=True, blank=True)
    responsible_membership_public_id = models.UUIDField(null=True, blank=True)
    capacity_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    capacity_unit_code = models.CharField(max_length=50, blank=True)
    meter_type_code = models.CharField(max_length=50, blank=True)
    current_meter_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    acquisition_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.CharField(max_length=3)
    next_service_on = models.DateField(null=True, blank=True)
    next_service_meter = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    compliance_due_on = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "equipmentops_asset"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "asset_code"],
                name="eqasset_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(current_meter_value__gte=0),
                name="eqasset_meter_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(acquisition_cost__gte=0),
                name="eqasset_cost_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(decommissioned_on__isnull=True)
                | models.Q(commissioned_on__isnull=True)
                | models.Q(decommissioned_on__gte=models.F("commissioned_on")),
                name="eqasset_dates_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "category_code"],
                name="eqasset_status_cat_idx",
            ),
            models.Index(
                fields=["company", "next_service_on"],
                name="eqasset_service_due_idx",
            ),
            models.Index(
                fields=["company", "compliance_due_on"],
                name="eqasset_compliance_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.policy_id and self.company_id and self.policy.company_id != self.company_id:
            raise ValidationError("Equipment policy cannot cross companies")
        if self.decommissioned_on and self.commissioned_on:
            if self.decommissioned_on < self.commissioned_on:
                raise ValidationError("Decommission date cannot precede commission date")
        if self.current_meter_value < 0:
            raise ValidationError({"current_meter_value": "Meter value cannot be negative"})
        if self.next_service_meter is not None and self.next_service_meter < 0:
            raise ValidationError({"next_service_meter": "Service meter cannot be negative"})
        if self.capacity_value is not None and self.capacity_value < 0:
            raise ValidationError({"capacity_value": "Capacity cannot be negative"})
        if self.capacity_value is not None and not self.capacity_unit_code:
            raise ValidationError({"capacity_unit_code": "Capacity unit is required"})
        if self.acquisition_cost < 0:
            raise ValidationError({"acquisition_cost": "Acquisition cost cannot be negative"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EquipmentDeployment(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_deployments",
    )
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name="deployments",
    )
    deployment_code = models.CharField(max_length=100)
    project_public_id = models.UUIDField(null=True, blank=True)
    location_public_id = models.UUIDField(null=True, blank=True)
    operator_employee_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=80)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    planned_meter_start = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    planned_meter_end = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    source_reference = models.CharField(max_length=150, blank=True)
    metadata = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "equipmentops_deployment"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "deployment_code"],
                name="eqdeploy_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="eqdeploy_date_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_meter_start__isnull=True)
                | models.Q(planned_meter_start__gte=0),
                name="eqdeploy_start_meter_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_meter_end__isnull=True)
                | models.Q(planned_meter_start__isnull=True)
                | models.Q(planned_meter_end__gte=models.F("planned_meter_start")),
                name="eqdeploy_meter_range_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "starts_at"],
                name="eqdeploy_status_start_idx",
            ),
            models.Index(
                fields=["asset", "status_code", "ends_at"],
                name="eqdeploy_asset_status_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.asset_id and self.company_id and self.asset.company_id != self.company_id:
            raise ValidationError("Equipment deployment cannot cross companies")
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError("Deployment ends_at must be after starts_at")
        if self.planned_meter_start is not None and self.planned_meter_start < 0:
            raise ValidationError("Planned meter start cannot be negative")
        if (
            self.planned_meter_end is not None
            and self.planned_meter_start is not None
            and self.planned_meter_end < self.planned_meter_start
        ):
            raise ValidationError("Planned meter end cannot precede start")
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EquipmentMeterReading(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_meter_readings",
    )
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name="meter_readings",
    )
    deployment = models.ForeignKey(
        EquipmentDeployment,
        on_delete=models.PROTECT,
        related_name="meter_readings",
        null=True,
        blank=True,
    )
    reading_at = models.DateTimeField()
    meter_type_code = models.CharField(max_length=50)
    reading_value = models.DecimalField(max_digits=18, decimal_places=2)
    source_code = models.CharField(max_length=80)
    recorded_by_public_id = models.UUIDField()
    evidence_object_key = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "equipmentops_meter_reading"
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "meter_type_code", "reading_at"],
                name="eqmeter_asset_type_time_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(reading_value__gte=0),
                name="eqmeter_value_nonneg_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "reading_at"],
                name="eqmeter_company_time_idx",
            ),
            models.Index(
                fields=["asset", "meter_type_code", "reading_at"],
                name="eqmeter_asset_time_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.asset_id and self.company_id and self.asset.company_id != self.company_id:
            raise ValidationError("Equipment reading cannot cross companies")
        if self.deployment_id:
            if self.company_id != self.deployment.company_id:
                raise ValidationError("Reading deployment cannot cross companies")
            if self.asset_id != self.deployment.asset_id:
                raise ValidationError("Reading deployment must belong to the same asset")
        if self.reading_value < 0:
            raise ValidationError({"reading_value": "Reading cannot be negative"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class MaintenanceWorkOrder(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_work_orders",
    )
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )
    code = models.CharField(max_length=100)
    maintenance_type_code = models.CharField(max_length=80)
    priority_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    reported_at = models.DateTimeField()
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    meter_at_open = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    summary = models.CharField(max_length=300)
    details = models.TextField(blank=True)
    vendor_public_id = models.UUIDField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency = models.CharField(max_length=3)
    requires_approval = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "equipmentops_maintenance_order"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="eqwork_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_cost__gte=0),
                name="eqwork_est_cost_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_cost__gte=0),
                name="eqwork_act_cost_nonneg_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(scheduled_end__isnull=True)
                | models.Q(scheduled_start__isnull=True)
                | models.Q(scheduled_end__gt=models.F("scheduled_start")),
                name="eqwork_schedule_range_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(completed_at__isnull=True)
                | models.Q(completed_at__gte=models.F("reported_at")),
                name="eqwork_complete_time_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "priority_code"],
                name="eqwork_status_priority_idx",
            ),
            models.Index(
                fields=["asset", "status_code", "scheduled_start"],
                name="eqwork_asset_schedule_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.asset_id and self.company_id and self.asset.company_id != self.company_id:
            raise ValidationError("Maintenance work order cannot cross companies")
        if self.scheduled_start and self.scheduled_end:
            if self.scheduled_end <= self.scheduled_start:
                raise ValidationError("Scheduled end must be after scheduled start")
        if self.completed_at and self.completed_at < self.reported_at:
            raise ValidationError("Completion cannot precede report time")
        if self.estimated_cost < 0 or self.actual_cost < 0:
            raise ValidationError("Maintenance costs cannot be negative")
        if self.meter_at_open is not None and self.meter_at_open < 0:
            raise ValidationError("Meter at open cannot be negative")
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EquipmentInspection(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_inspections",
    )
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name="inspections",
    )
    inspection_code = models.CharField(max_length=100)
    inspection_type_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    result_code = models.CharField(max_length=80)
    inspected_at = models.DateTimeField()
    valid_until = models.DateField(null=True, blank=True)
    inspector_public_id = models.UUIDField()
    score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    findings_count = models.PositiveIntegerField(default=0)
    certificate_reference = models.CharField(max_length=150, blank=True)
    evidence_object_key = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "equipmentops_inspection"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "inspection_code"],
                name="eqinspect_company_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=0),
                name="eqinspect_score_nonneg_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "valid_until", "result_code"],
                name="eqinspect_valid_result_idx",
            ),
            models.Index(
                fields=["asset", "inspected_at"],
                name="eqinspect_asset_time_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.asset_id and self.company_id and self.asset.company_id != self.company_id:
            raise ValidationError("Equipment inspection cannot cross companies")
        if self.valid_until and self.valid_until < self.inspected_at.date():
            raise ValidationError("Inspection validity cannot precede inspection date")
        if self.score is not None and self.score < 0:
            raise ValidationError({"score": "Inspection score cannot be negative"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EquipmentApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_approvals",
    )
    work_order = models.ForeignKey(
        MaintenanceWorkOrder,
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
        db_table = "equipmentops_approval"
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "step_code"],
                name="eqapproval_order_step_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status_code", "requested_at"],
                name="eqapproval_status_idx",
            ),
            models.Index(
                fields=["company", "due_at", "decided_at"],
                name="eqapproval_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.work_order_id
            and self.company_id
            and self.work_order.company_id != self.company_id
        ):
            raise ValidationError("Equipment approval cannot cross companies")
        if self.decided_at and not self.decision_code:
            raise ValidationError({"decision_code": "Decision code is required"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})


class EquipmentRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="equipment_risks",
    )
    asset = models.ForeignKey(
        EquipmentAsset,
        on_delete=models.PROTECT,
        related_name="risks",
    )
    work_order = models.ForeignKey(
        MaintenanceWorkOrder,
        on_delete=models.PROTECT,
        related_name="risks",
        null=True,
        blank=True,
    )
    risk_code = models.CharField(max_length=100)
    severity_code = models.CharField(max_length=80)
    status_code = models.CharField(max_length=80)
    message = models.CharField(max_length=1000)
    due_at = models.DateTimeField(null=True, blank=True)
    assigned_to_membership_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolution_code = models.CharField(max_length=80, blank=True)
    resolution_note = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "equipmentops_risk"
        indexes = [
            models.Index(
                fields=["company", "status_code", "severity_code"],
                name="eqrisk_status_severity_idx",
            ),
            models.Index(
                fields=["asset", "resolved_at", "due_at"],
                name="eqrisk_asset_due_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.asset_id and self.company_id and self.asset.company_id != self.company_id:
            raise ValidationError("Equipment risk cannot cross companies")
        if self.work_order_id:
            if self.company_id != self.work_order.company_id:
                raise ValidationError("Risk work order cannot cross companies")
            if self.asset_id != self.work_order.asset_id:
                raise ValidationError("Risk work order must belong to the same asset")
        if self.resolved_at and not self.resolution_code:
            raise ValidationError({"resolution_code": "Resolution code is required"})
        if not isinstance(self.metadata or {}, dict):
            raise ValidationError({"metadata": "Metadata must be an object"})
