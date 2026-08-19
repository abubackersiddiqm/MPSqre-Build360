from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class DigitalTwinPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="digital_twin_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    coordinate_system_code = models.CharField(max_length=80, default="PROJECT_LOCAL")
    model_review_frequency_code = models.CharField(max_length=30, default="WEEKLY")
    telemetry_retention_days = models.PositiveIntegerField(default=365)
    alert_acknowledgement_minutes = models.PositiveIntegerField(default=30)
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "twinops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="twin_policy_version_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="twin_policy_dates_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="twin_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)
        self.coordinate_system_code = normalize_code(self.coordinate_system_code)
        self.model_review_frequency_code = normalize_code(self.model_review_frequency_code)


class BIMModel(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="bim_models")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    discipline_code = models.CharField(max_length=60)
    model_type_code = models.CharField(max_length=40, default="AUTHORING")
    file_format_code = models.CharField(max_length=30, default="IFC")
    authoring_tool = models.CharField(max_length=160, blank=True)
    coordinate_system_code = models.CharField(max_length=80, default="PROJECT_LOCAL")
    storage_reference = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    current_revision_code = models.CharField(max_length=40, blank=True)
    last_published_at = models.DateTimeField(null=True, blank=True)
    model_metadata = models.JSONField(default=dict, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_model"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="twin_model_code_uq")]
        indexes = [
            models.Index(fields=["company", "project_public_id", "status_code"], name="twin_model_project_idx"),
            models.Index(fields=["company", "discipline_code"], name="twin_model_discipline_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.discipline_code = normalize_code(self.discipline_code)
        self.model_type_code = normalize_code(self.model_type_code)
        self.file_format_code = normalize_code(self.file_format_code)
        self.coordinate_system_code = normalize_code(self.coordinate_system_code)
        self.status_code = normalize_code(self.status_code)
        if self.checksum_sha256 and len(self.checksum_sha256) != 64:
            raise ValidationError({"checksum_sha256": "SHA-256 checksum must contain 64 hexadecimal characters."})


class BIMRevision(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="bim_revisions")
    model = models.ForeignKey(BIMModel, on_delete=models.PROTECT, related_name="revisions")
    revision_code = models.CharField(max_length=40)
    issue_purpose_code = models.CharField(max_length=60, default="COORDINATION")
    file_reference = models.CharField(max_length=500)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    authored_by_public_id = models.UUIDField()
    status_code = models.CharField(max_length=30, default="DRAFT")
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_revision"
        constraints = [models.UniqueConstraint(fields=["model", "revision_code"], name="twin_revision_code_uq")]
        indexes = [models.Index(fields=["company", "status_code", "created_at"], name="twin_revision_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.revision_code = normalize_code(self.revision_code)
        self.issue_purpose_code = normalize_code(self.issue_purpose_code)
        self.status_code = normalize_code(self.status_code)
        if self.model_id and self.model.company_id != self.company_id:
            raise ValidationError("BIM revision cannot cross companies.")
        if self.checksum_sha256 and len(self.checksum_sha256) != 64:
            raise ValidationError({"checksum_sha256": "SHA-256 checksum must contain 64 hexadecimal characters."})


class ModelFederation(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="model_federations")
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    project_public_id = models.UUIDField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    model_public_ids = models.JSONField(default=list, blank=True)
    model_count = models.PositiveIntegerField(default=0)
    coordination_date = models.DateField(null=True, blank=True)
    prepared_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_federation"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="twin_federation_code_uq")]
        indexes = [models.Index(fields=["company", "project_public_id", "status_code"], name="twin_federation_project_idx")]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.model_public_ids, list):
            raise ValidationError({"model_public_ids": "Model references must be supplied as a list."})


class ClashRecord(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="bim_clashes")
    federation = models.ForeignKey(ModelFederation, on_delete=models.PROTECT, related_name="clashes")
    clash_number = models.CharField(max_length=80)
    clash_type_code = models.CharField(max_length=60, default="HARD")
    severity_code = models.CharField(max_length=30, default="MEDIUM")
    discipline_a_code = models.CharField(max_length=60)
    discipline_b_code = models.CharField(max_length=60)
    element_a_reference = models.CharField(max_length=200, blank=True)
    element_b_reference = models.CharField(max_length=200, blank=True)
    location_reference = models.CharField(max_length=240, blank=True)
    coordinates = models.JSONField(default=dict, blank=True)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="OPEN")
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_clash"
        constraints = [models.UniqueConstraint(fields=["federation", "clash_number"], name="twin_clash_number_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="twin_clash_status_idx"),
            models.Index(fields=["company", "due_date"], name="twin_clash_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.clash_number = normalize_code(self.clash_number)
        self.clash_type_code = normalize_code(self.clash_type_code)
        self.severity_code = normalize_code(self.severity_code)
        self.discipline_a_code = normalize_code(self.discipline_a_code)
        self.discipline_b_code = normalize_code(self.discipline_b_code)
        self.status_code = normalize_code(self.status_code)
        if self.federation_id and self.federation.company_id != self.company_id:
            raise ValidationError("Clash record cannot cross companies.")


class BIMIssue(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="bim_issues")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    model = models.ForeignKey(BIMModel, on_delete=models.PROTECT, related_name="issues", null=True, blank=True)
    revision = models.ForeignKey(BIMRevision, on_delete=models.PROTECT, related_name="issues", null=True, blank=True)
    issue_code = models.CharField(max_length=80)
    category_code = models.CharField(max_length=60, default="COORDINATION")
    priority_code = models.CharField(max_length=30, default="NORMAL")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status_code = models.CharField(max_length=30, default="OPEN")
    assigned_to_public_id = models.UUIDField(null=True, blank=True)
    raised_by_public_id = models.UUIDField()
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_issue"
        constraints = [models.UniqueConstraint(fields=["company", "issue_code"], name="twin_issue_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "priority_code"], name="twin_issue_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="twin_issue_project_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.issue_code = normalize_code(self.issue_code)
        self.category_code = normalize_code(self.category_code)
        self.priority_code = normalize_code(self.priority_code)
        self.status_code = normalize_code(self.status_code)
        if self.model_id and self.model.company_id != self.company_id:
            raise ValidationError("BIM issue model cannot cross companies.")
        if self.revision_id and self.revision.company_id != self.company_id:
            raise ValidationError("BIM issue revision cannot cross companies.")


class IoTDevice(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="smart_site_devices")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    device_type_code = models.CharField(max_length=60)
    external_device_reference = models.CharField(max_length=200, blank=True)
    provider_code = models.CharField(max_length=80, default="GENERIC")
    protocol_code = models.CharField(max_length=40, default="HTTP")
    metric_code = models.CharField(max_length=80)
    unit_code = models.CharField(max_length=40)
    status_code = models.CharField(max_length=30, default="REGISTERED")
    threshold_configuration = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=80, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_device"
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="twin_device_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "last_seen_at"], name="twin_device_status_idx"),
            models.Index(fields=["company", "project_public_id"], name="twin_device_project_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = normalize_code(self.code)
        self.device_type_code = normalize_code(self.device_type_code)
        self.provider_code = normalize_code(self.provider_code)
        self.protocol_code = normalize_code(self.protocol_code)
        self.metric_code = normalize_code(self.metric_code)
        self.unit_code = normalize_code(self.unit_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.threshold_configuration, dict):
            raise ValidationError({"threshold_configuration": "Threshold configuration must be a JSON object."})


class TelemetryReading(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="smart_site_telemetry")
    device = models.ForeignKey(IoTDevice, on_delete=models.PROTECT, related_name="readings")
    observed_at = models.DateTimeField()
    metric_code = models.CharField(max_length=80)
    numeric_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    text_value = models.CharField(max_length=500, blank=True)
    unit_code = models.CharField(max_length=40)
    quality_code = models.CharField(max_length=30, default="GOOD")
    source_reference = models.CharField(max_length=300, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "twinops_telemetry"
        indexes = [
            models.Index(fields=["company", "device", "observed_at"], name="twin_telemetry_device_idx"),
            models.Index(fields=["company", "metric_code", "observed_at"], name="twin_telemetry_metric_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.metric_code = normalize_code(self.metric_code)
        self.unit_code = normalize_code(self.unit_code)
        self.quality_code = normalize_code(self.quality_code)
        if self.device_id and self.device.company_id != self.company_id:
            raise ValidationError("Telemetry reading cannot cross companies.")
        if self.numeric_value is None and not self.text_value:
            raise ValidationError("Telemetry reading requires a numeric or text value.")


class SmartAlert(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="smart_site_alerts")
    device = models.ForeignKey(IoTDevice, on_delete=models.PROTECT, related_name="alerts", null=True, blank=True)
    project_public_id = models.UUIDField(null=True, blank=True)
    alert_code = models.CharField(max_length=80)
    alert_type_code = models.CharField(max_length=60)
    severity_code = models.CharField(max_length=30, default="MEDIUM")
    status_code = models.CharField(max_length=30, default="OPEN")
    message = models.TextField()
    triggered_at = models.DateTimeField()
    acknowledged_by_public_id = models.UUIDField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by_public_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    source_reading_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_alert"
        constraints = [models.UniqueConstraint(fields=["company", "alert_code"], name="twin_alert_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="twin_alert_status_idx"),
            models.Index(fields=["company", "triggered_at"], name="twin_alert_time_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.alert_code = normalize_code(self.alert_code)
        self.alert_type_code = normalize_code(self.alert_type_code)
        self.severity_code = normalize_code(self.severity_code)
        self.status_code = normalize_code(self.status_code)
        if self.device_id and self.device.company_id != self.company_id:
            raise ValidationError("Smart alert cannot cross companies.")


class HandoverAssetRecord(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="digital_handover_assets")
    project_public_id = models.UUIDField(null=True, blank=True)
    site_reference = models.CharField(max_length=160, blank=True)
    asset_tag = models.CharField(max_length=100)
    asset_name = models.CharField(max_length=240)
    classification_code = models.CharField(max_length=80)
    model = models.ForeignKey(BIMModel, on_delete=models.PROTECT, related_name="handover_assets", null=True, blank=True)
    model_element_reference = models.CharField(max_length=200, blank=True)
    serial_number = models.CharField(max_length=160, blank=True)
    manufacturer = models.CharField(max_length=240, blank=True)
    location_reference = models.CharField(max_length=240, blank=True)
    commissioned_on = models.DateField(null=True, blank=True)
    warranty_end_on = models.DateField(null=True, blank=True)
    operation_status_code = models.CharField(max_length=40, default="DRAFT")
    maintainable = models.BooleanField(default=True)
    document_references = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    captured_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "twinops_asset"
        constraints = [
            models.UniqueConstraint(fields=["company", "asset_tag"], name="twin_asset_tag_uq"),
            models.CheckConstraint(
                condition=models.Q(warranty_end_on__isnull=True)
                | models.Q(commissioned_on__isnull=True)
                | models.Q(warranty_end_on__gte=models.F("commissioned_on")),
                name="twin_asset_warranty_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "project_public_id", "operation_status_code"], name="twin_asset_project_idx"),
            models.Index(fields=["company", "classification_code"], name="twin_asset_class_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.asset_tag = normalize_code(self.asset_tag)
        self.classification_code = normalize_code(self.classification_code)
        self.operation_status_code = normalize_code(self.operation_status_code)
        if self.model_id and self.model.company_id != self.company_id:
            raise ValidationError("Handover asset cannot cross companies.")
        if not isinstance(self.document_references, list):
            raise ValidationError({"document_references": "Document references must be supplied as a list."})
        if not isinstance(self.attributes, dict):
            raise ValidationError({"attributes": "Asset attributes must be supplied as a JSON object."})
