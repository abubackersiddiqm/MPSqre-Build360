from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class FacilityPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    preventive_horizon_days = models.PositiveIntegerField(default=90)
    warranty_alert_days = models.PositiveIntegerField(default=60)
    service_response_minutes = models.PositiveIntegerField(default=240)
    service_resolution_minutes = models.PositiveIntegerField(default=1440)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "facilityops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="fac_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="fac_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="fac_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class Facility(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="managed_facilities")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    facility_type_code = models.CharField(max_length=60, default="BUILDING")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    address = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=80, blank=True)
    gross_area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    occupancy_capacity = models.PositiveIntegerField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    operational_from = models.DateField(null=True, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_facility"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="fac_facility_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code"], name="fac_facility_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="fac_facility_project_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.facility_type_code = normalize_code(self.facility_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.address, dict):
            raise ValidationError({"address": "Facility address must be a JSON object."})


class FacilitySpace(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_spaces")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="spaces")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, related_name="children", null=True, blank=True)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    space_type_code = models.CharField(max_length=60, default="ROOM")
    floor_reference = models.CharField(max_length=80, blank=True)
    area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    criticality_code = models.CharField(max_length=30, default="NORMAL")
    status_code = models.CharField(max_length=30, default="ACTIVE")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_space"
        constraints = [models.UniqueConstraint(fields=["facility", "code"], name="fac_space_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code"], name="fac_space_status_idx"),
            models.Index(fields=["company", "facility", "parent"], name="fac_space_parent_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.space_type_code = normalize_code(self.space_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.criticality_code = normalize_code(self.criticality_code)
        self.status_code = normalize_code(self.status_code)
        if self.facility_id and self.facility.company_id != self.company_id:
            raise ValidationError("Facility space cannot cross companies.")
        if self.parent_id:
            if self.parent.company_id != self.company_id or self.parent.facility_id != self.facility_id:
                raise ValidationError("Parent space must belong to the same company and facility.")
            if self.pk and self.parent_id == self.pk:
                raise ValidationError("A space cannot be its own parent.")


class OperationalAsset(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="operational_assets")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="assets")
    space = models.ForeignKey(FacilitySpace, on_delete=models.PROTECT, related_name="assets", null=True, blank=True)
    asset_tag = models.CharField(max_length=100)
    asset_name = models.CharField(max_length=240)
    classification_code = models.CharField(max_length=80)
    source_handover_public_id = models.UUIDField(null=True, blank=True)
    model_element_reference = models.CharField(max_length=200, blank=True)
    manufacturer = models.CharField(max_length=240, blank=True)
    model_number = models.CharField(max_length=160, blank=True)
    serial_number = models.CharField(max_length=160, blank=True)
    commissioned_on = models.DateField(null=True, blank=True)
    warranty_start_on = models.DateField(null=True, blank=True)
    warranty_end_on = models.DateField(null=True, blank=True)
    criticality_code = models.CharField(max_length=30, default="NORMAL")
    condition_code = models.CharField(max_length=30, default="GOOD")
    operation_status_code = models.CharField(max_length=40, default="DRAFT")
    maintainable = models.BooleanField(default=True)
    service_interval_days = models.PositiveIntegerField(null=True, blank=True)
    last_service_on = models.DateField(null=True, blank=True)
    next_service_on = models.DateField(null=True, blank=True)
    document_references = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    captured_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_asset"
        constraints = [
            models.UniqueConstraint(fields=["company", "asset_tag"], name="fac_asset_tag_uq"),
            models.CheckConstraint(
                condition=models.Q(warranty_end_on__isnull=True)
                | models.Q(warranty_start_on__isnull=True)
                | models.Q(warranty_end_on__gte=models.F("warranty_start_on")),
                name="fac_asset_warranty_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "operation_status_code", "criticality_code"], name="fac_asset_status_idx"),
            models.Index(fields=["company", "next_service_on"], name="fac_asset_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.asset_tag = normalize_code(self.asset_tag)
        self.classification_code = normalize_code(self.classification_code)
        self.criticality_code = normalize_code(self.criticality_code)
        self.condition_code = normalize_code(self.condition_code)
        self.operation_status_code = normalize_code(self.operation_status_code)
        if self.facility_id and self.facility.company_id != self.company_id:
            raise ValidationError("Operational asset cannot cross companies.")
        if self.space_id and (self.space.company_id != self.company_id or self.space.facility_id != self.facility_id):
            raise ValidationError("Operational asset space must belong to the same company and facility.")
        if not isinstance(self.document_references, list):
            raise ValidationError({"document_references": "Document references must be supplied as a list."})
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Asset attributes must be supplied as a JSON object."})


class MaintenancePlan(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_maintenance_plans")
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="maintenance_plans")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    plan_type_code = models.CharField(max_length=40, default="PREVENTIVE")
    frequency_days = models.PositiveIntegerField()
    lead_time_days = models.PositiveIntegerField(default=7)
    next_due_date = models.DateField()
    estimated_duration_minutes = models.PositiveIntegerField(default=60)
    checklist = models.JSONField(default=list, blank=True)
    status_code = models.CharField(max_length=30, default="ACTIVE")
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_plan"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="fac_plan_code_uq")]
        indexes = [
            models.Index(fields=["company", "next_due_date", "status_code"], name="fac_plan_due_idx"),
            models.Index(fields=["company", "asset", "status_code"], name="fac_plan_status_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.plan_type_code = normalize_code(self.plan_type_code)
        self.status_code = normalize_code(self.status_code)
        if self.asset_id and self.asset.company_id != self.company_id:
            raise ValidationError("Maintenance plan cannot cross companies.")
        if not isinstance(self.checklist, list):
            raise ValidationError({"checklist": "Maintenance checklist must be supplied as a list."})


class ServiceRequest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_service_requests")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="service_requests")
    space = models.ForeignKey(FacilitySpace, on_delete=models.PROTECT, related_name="service_requests", null=True, blank=True)
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="service_requests", null=True, blank=True)
    request_number = models.CharField(max_length=80)
    category_code = models.CharField(max_length=60, default="GENERAL")
    priority_code = models.CharField(max_length=30, default="NORMAL")
    channel_code = models.CharField(max_length=30, default="PORTAL")
    requester_public_id = models.UUIDField(null=True, blank=True)
    requester_reference = models.CharField(max_length=160, blank=True)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="NEW")
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closure_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_request"
        constraints = [models.UniqueConstraint(fields=["company", "request_number"], name="fac_request_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="fac_request_status_idx"),
            models.Index(fields=["company", "resolution_due_at"], name="fac_request_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.request_number = normalize_code(self.request_number)
        self.category_code = normalize_code(self.category_code)
        self.priority_code = normalize_code(self.priority_code)
        self.channel_code = normalize_code(self.channel_code)
        self.status_code = normalize_code(self.status_code)
        if self.facility_id and self.facility.company_id != self.company_id:
            raise ValidationError("Service request cannot cross companies.")
        if self.space_id and (self.space.company_id != self.company_id or self.space.facility_id != self.facility_id):
            raise ValidationError("Service request space must belong to the same facility.")
        if self.asset_id and (self.asset.company_id != self.company_id or self.asset.facility_id != self.facility_id):
            raise ValidationError("Service request asset must belong to the same facility.")


class FacilityWorkOrder(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_work_orders")
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="work_orders")
    plan = models.ForeignKey(MaintenancePlan, on_delete=models.PROTECT, related_name="work_orders", null=True, blank=True)
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name="work_orders", null=True, blank=True)
    work_order_number = models.CharField(max_length=80)
    work_type_code = models.CharField(max_length=40, default="CORRECTIVE")
    priority_code = models.CharField(max_length=30, default="NORMAL")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    vendor_reference = models.CharField(max_length=200, blank=True)
    due_date = models.DateField(null=True, blank=True)
    scheduled_start_at = models.DateTimeField(null=True, blank=True)
    scheduled_end_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    completion_evidence = models.JSONField(default=dict, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_work_order"
        constraints = [models.UniqueConstraint(fields=["company", "work_order_number"], name="fac_wo_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="fac_wo_status_idx"),
            models.Index(fields=["company", "due_date"], name="fac_wo_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.work_order_number = normalize_code(self.work_order_number)
        self.work_type_code = normalize_code(self.work_type_code)
        self.priority_code = normalize_code(self.priority_code)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = normalize_code(self.currency_code)
        if self.asset_id and self.asset.company_id != self.company_id:
            raise ValidationError("Facility work order cannot cross companies.")
        if self.plan_id and (self.plan.company_id != self.company_id or self.plan.asset_id != self.asset_id):
            raise ValidationError("Maintenance plan must belong to the same asset and company.")
        if self.service_request_id and (
            self.service_request.company_id != self.company_id or self.service_request.facility_id != self.asset.facility_id
        ):
            raise ValidationError("Service request must belong to the same facility and company.")
        if not isinstance(self.completion_evidence, dict):
            raise ValidationError({"completion_evidence": "Completion evidence must be supplied as a JSON object."})


class WarrantyClaim(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_warranty_claims")
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="warranty_claims")
    work_order = models.ForeignKey(FacilityWorkOrder, on_delete=models.PROTECT, related_name="warranty_claims", null=True, blank=True)
    claim_number = models.CharField(max_length=80)
    supplier_reference = models.CharField(max_length=200, blank=True)
    warranty_reference = models.CharField(max_length=200, blank=True)
    reported_on = models.DateField()
    failure_date = models.DateField(null=True, blank=True)
    issue_description = models.TextField()
    claimed_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    status_code = models.CharField(max_length=30, default="DRAFT")
    filed_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    owner_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_warranty"
        constraints = [models.UniqueConstraint(fields=["company", "claim_number"], name="fac_claim_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code"], name="fac_claim_status_idx"),
            models.Index(fields=["company", "reported_on"], name="fac_claim_date_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.claim_number = normalize_code(self.claim_number)
        self.status_code = normalize_code(self.status_code)
        self.currency_code = normalize_code(self.currency_code)
        if self.asset_id and self.asset.company_id != self.company_id:
            raise ValidationError("Warranty claim cannot cross companies.")
        if self.work_order_id and (self.work_order.company_id != self.company_id or self.work_order.asset_id != self.asset_id):
            raise ValidationError("Warranty claim work order must belong to the same asset and company.")


class ConditionInspection(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_condition_inspections")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="condition_inspections")
    space = models.ForeignKey(FacilitySpace, on_delete=models.PROTECT, related_name="condition_inspections", null=True, blank=True)
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="condition_inspections", null=True, blank=True)
    inspection_number = models.CharField(max_length=80)
    inspection_type_code = models.CharField(max_length=60, default="CONDITION")
    scheduled_on = models.DateField(null=True, blank=True)
    inspected_on = models.DateField(null=True, blank=True)
    condition_code = models.CharField(max_length=30, default="GOOD")
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    findings = models.TextField(blank=True)
    actions_required = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    inspector_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "facilityops_inspection"
        constraints = [models.UniqueConstraint(fields=["company", "inspection_number"], name="fac_insp_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "condition_code"], name="fac_insp_status_idx"),
            models.Index(fields=["company", "scheduled_on"], name="fac_insp_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.inspection_number = normalize_code(self.inspection_number)
        self.inspection_type_code = normalize_code(self.inspection_type_code)
        self.condition_code = normalize_code(self.condition_code)
        self.status_code = normalize_code(self.status_code)
        if self.facility_id and self.facility.company_id != self.company_id:
            raise ValidationError("Condition inspection cannot cross companies.")
        if self.space_id and (self.space.company_id != self.company_id or self.space.facility_id != self.facility_id):
            raise ValidationError("Inspection space must belong to the same facility.")
        if self.asset_id and (self.asset.company_id != self.company_id or self.asset.facility_id != self.facility_id):
            raise ValidationError("Inspection asset must belong to the same facility.")
        if not isinstance(self.evidence, dict):
            raise ValidationError({"evidence": "Inspection evidence must be supplied as a JSON object."})


class AssetLifecycleEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="facility_asset_events")
    asset = models.ForeignKey(OperationalAsset, on_delete=models.PROTECT, related_name="lifecycle_events")
    event_type_code = models.CharField(max_length=60)
    occurred_at = models.DateTimeField()
    from_status_code = models.CharField(max_length=40, blank=True)
    to_status_code = models.CharField(max_length=40, blank=True)
    summary = models.CharField(max_length=300)
    reference = models.CharField(max_length=300, blank=True)
    event_metadata = models.JSONField(default=dict, blank=True)
    recorded_by_public_id = models.UUIDField()

    class Meta:
        db_table = "facilityops_event"
        indexes = [
            models.Index(fields=["company", "asset", "occurred_at"], name="fac_event_asset_idx"),
            models.Index(fields=["company", "event_type_code"], name="fac_event_type_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.event_type_code = normalize_code(self.event_type_code)
        self.from_status_code = normalize_code(self.from_status_code) if self.from_status_code else ""
        self.to_status_code = normalize_code(self.to_status_code) if self.to_status_code else ""
        if self.asset_id and self.asset.company_id != self.company_id:
            raise ValidationError("Asset lifecycle event cannot cross companies.")
        if not isinstance(self.event_metadata, dict):
            raise ValidationError({"event_metadata": "Lifecycle event metadata must be supplied as a JSON object."})
