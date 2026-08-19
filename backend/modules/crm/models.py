from __future__ import annotations

from decimal import Decimal

from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


class TenantOwnedModel(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT)

    class Meta:
        abstract = True




class CrmTenantProfile(TenantOwnedModel):
    class IndustryCode(models.TextChoices):
        GENERAL = "general", "General business"
        CONSTRUCTION = "construction", "Construction"
        REAL_ESTATE = "real_estate", "Real estate"
        INTERIOR = "interior", "Interior design"
        AUTOMOBILE = "automobile", "Automobile"
        FINANCIAL_SERVICES = "financial_services", "Financial services"
        MANUFACTURING = "manufacturing", "Manufacturing"
        PROFESSIONAL_SERVICES = "professional_services", "Professional services"
        OTHER = "other", "Other / custom"

    industry_code = models.CharField(
        max_length=80,
        choices=IndustryCode.choices,
        default=IndustryCode.GENERAL,
    )
    terminology = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_tenant_profile"
        constraints = [
            models.UniqueConstraint(fields=["company"], name="crm_profile_company_uq"),
        ]


class CrmPipeline(TenantOwnedModel):
    class EntityType(models.TextChoices):
        LEAD = "lead", "Lead"
        OPPORTUNITY = "opportunity", "Opportunity"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    source_pack_code = models.CharField(max_length=80, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_pipeline"
        ordering = ["entity_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "code"],
                name="crm_pipeline_company_code_uq",
            ),
            models.UniqueConstraint(
                fields=["company", "entity_type"],
                condition=models.Q(is_default=True, is_active=True),
                name="crm_pipeline_default_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="crm_pipeline_active_idx",
            )
        ]


class CrmLeadSource(TenantOwnedModel):
    class ChannelType(models.TextChoices):
        MANUAL = "manual", "Manual"
        WEBSITE = "website", "Website"
        ADS = "ads", "Ads"
        SOCIAL = "social", "Social"
        PHONE = "phone", "Phone"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        REFERRAL = "referral", "Referral"
        PARTNER = "partner", "Partner"
        EVENT = "event", "Event"
        IMPORT = "import", "Import"
        API = "api", "API"
        OTHER = "other", "Other"

    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    channel_type = models.CharField(
        max_length=30,
        choices=ChannelType.choices,
        default=ChannelType.MANUAL,
    )
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    source_pack_code = models.CharField(max_length=80, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_lead_source"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="crm_source_company_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "is_active", "sort_order"],
                name="crm_source_active_idx",
            )
        ]


class CrmCustomFieldDefinition(TenantOwnedModel):
    class EntityType(models.TextChoices):
        CUSTOMER = "customer", "Customer / account"
        CONTACT = "contact", "Contact"
        LEAD = "lead", "Lead"
        OPPORTUNITY = "opportunity", "Opportunity"

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        LONG_TEXT = "long_text", "Long text"
        NUMBER = "number", "Number"
        CURRENCY = "currency", "Currency"
        PERCENT = "percent", "Percentage"
        DATE = "date", "Date"
        DATETIME = "datetime", "Date & time"
        SELECT = "select", "Dropdown"
        MULTISELECT = "multiselect", "Multi-select"
        BOOLEAN = "boolean", "Yes / no"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        URL = "url", "URL"
        USER = "user", "User"
        LOOKUP = "lookup", "Lookup"
        FILE = "file", "File"
        FORMULA = "formula", "Formula"

    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    field_type = models.CharField(max_length=30, choices=FieldType.choices)
    help_text = models.CharField(max_length=500, blank=True)
    is_required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    validation = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    source_pack_code = models.CharField(max_length=80, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_custom_field_definition"
        ordering = ["entity_type", "sort_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "code"],
                name="crm_custom_field_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="crm_custom_field_active_idx",
            )
        ]


class PipelineStage(TenantOwnedModel):
    class EntityType(models.TextChoices):
        LEAD = "lead", "Lead"
        OPPORTUNITY = "opportunity", "Opportunity"

    class Outcome(models.TextChoices):
        OPEN = "open", "Open"
        QUALIFIED = "qualified", "Qualified"
        DISQUALIFIED = "disqualified", "Disqualified"
        CONVERTED = "converted", "Converted"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    pipeline = models.ForeignKey(
        CrmPipeline,
        on_delete=models.PROTECT,
        related_name="stages",
        null=True,
        blank=True,
    )
    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    outcome = models.CharField(max_length=30, choices=Outcome.choices, default=Outcome.OPEN)
    sort_order = models.PositiveIntegerField(default=100)
    probability_percent = models.PositiveSmallIntegerField(default=0)
    allowed_next_codes = models.JSONField(default=list)
    is_initial = models.BooleanField(default=False)
    allows_conversion = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_pipeline_stage"
        ordering = ["entity_type", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "pipeline", "code"],
                name="crm_stage_pipeline_code_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(probability_percent__lte=100),
                name="crm_stage_prob_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="crm_stage_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "is_active", "sort_order"],
                name="crm_stage_active_idx",
            )
        ]


class Customer(TenantOwnedModel):
    class Kind(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        PERSON = "person", "Person"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    kind = models.CharField(max_length=30, choices=Kind.choices)
    display_name = models.CharField(max_length=250)
    legal_name = models.CharField(max_length=250, blank=True)
    normalized_name = models.CharField(max_length=250)
    external_reference = models.CharField(max_length=120, blank=True)
    source_code = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    version = models.PositiveBigIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_customer"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "external_reference"],
                condition=~models.Q(external_reference=""),
                name="crm_customer_extref_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "normalized_name"],
                name="crm_customer_lookup_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "status"],
                name="crm_customer_owner_idx",
            ),
        ]


class Contact(TenantOwnedModel):
    class ConsentStatus(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="contacts",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    job_title = models.CharField(max_length=160, blank=True)
    email_ciphertext = models.TextField(blank=True)
    email_blind_index = models.CharField(max_length=64, blank=True)
    phone_ciphertext = models.TextField(blank=True)
    phone_blind_index = models.CharField(max_length=64, blank=True)
    alternate_phone_ciphertext = models.TextField(blank=True)
    alternate_phone_blind_index = models.CharField(max_length=64, blank=True)
    email_last_four = models.CharField(max_length=4, blank=True)
    phone_last_four = models.CharField(max_length=4, blank=True)
    alternate_phone_last_four = models.CharField(max_length=4, blank=True)
    consent_status = models.CharField(
        max_length=30,
        choices=ConsentStatus.choices,
        default=ConsentStatus.UNKNOWN,
    )
    preferred_channel_code = models.CharField(max_length=40, blank=True)
    address = models.JSONField(default=dict, blank=True)
    source_code = models.CharField(max_length=80, blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    owner_membership_public_id = models.UUIDField(null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_contact"
        indexes = [
            models.Index(
                fields=["company", "email_blind_index"],
                name="crm_contact_email_idx",
            ),
            models.Index(
                fields=["company", "phone_blind_index"],
                name="crm_contact_phone_idx",
            ),
            models.Index(
                fields=["company", "alternate_phone_blind_index"],
                name="crm_contact_alt_phone_idx",
            ),
            models.Index(
                fields=["company", "customer", "is_active"],
                name="crm_contact_customer_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "is_active"],
                name="crm_contact_owner_idx",
            ),
            models.Index(
                fields=["company", "is_active", "first_name", "last_name"],
                name="crm_contact_name_idx",
            ),
        ]


class Lead(TenantOwnedModel):
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    source_code = models.CharField(max_length=80, blank=True)
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name="leads")
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="leads",
        null=True,
        blank=True,
    )
    primary_contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="leads",
        null=True,
        blank=True,
    )
    owner_membership_public_id = models.UUIDField()
    estimated_value = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    qualified_at = models.DateTimeField(null=True, blank=True)
    disqualified_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    closed_reason_code = models.CharField(max_length=100, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_lead"
        indexes = [
            models.Index(
                fields=["company", "stage", "next_follow_up_at"],
                name="crm_lead_stage_follow_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "stage"],
                name="crm_lead_owner_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "next_follow_up_at"],
                name="crm_lead_owner_follow_idx",
            ),
            models.Index(
                fields=["company", "created_at"],
                name="crm_lead_created_idx",
            ),
            models.Index(
                fields=["company", "primary_contact", "next_follow_up_at"],
                name="crm_lead_contact_follow_idx",
            ),
        ]


class Opportunity(TenantOwnedModel):
    name = models.CharField(max_length=250)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="opportunities")
    primary_contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    source_lead = models.ForeignKey(
        Lead,
        on_delete=models.PROTECT,
        related_name="opportunities",
        null=True,
        blank=True,
    )
    stage = models.ForeignKey(
        PipelineStage,
        on_delete=models.PROTECT,
        related_name="opportunities",
    )
    owner_membership_public_id = models.UUIDField()
    amount = models.DecimalField(max_digits=19, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    expected_close_date = models.DateField(null=True, blank=True)
    probability_percent = models.PositiveSmallIntegerField(default=0)
    custom_fields = models.JSONField(default=dict, blank=True)
    won_at = models.DateTimeField(null=True, blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)
    close_reason_code = models.CharField(max_length=100, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_opportunity"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(probability_percent__lte=100),
                name="crm_opp_prob_valid",
            ),
            models.UniqueConstraint(
                fields=["company", "source_lead"],
                condition=models.Q(source_lead__isnull=False),
                name="crm_opp_source_lead_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "stage", "expected_close_date"],
                name="crm_opp_stage_close_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "stage"],
                name="crm_opp_owner_idx",
            ),
            models.Index(
                fields=["company", "primary_contact", "stage"],
                name="crm_opp_contact_stage_idx",
            ),
        ]


class Activity(TenantOwnedModel):
    class ActivityType(models.TextChoices):
        NOTE = "note", "Note"
        CALL = "call", "Call"
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        SITE_VISIT = "site_visit", "Site visit"
        FOLLOW_UP = "follow_up", "Follow-up"
        VOICE_NOTE = "voice_note", "Voice note"
        DOCUMENT = "document", "Document"
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"
        TASK = "task", "Task"
        STATUS_CHANGE = "status_change", "Status change"
        ASSIGNMENT_CHANGE = "assignment_change", "Assignment change"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Direction(models.TextChoices):
        INTERNAL = "internal", "Internal"
        OUTBOUND = "outbound", "Outbound"
        INBOUND = "inbound", "Inbound"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PLANNED)
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        default=Direction.INTERNAL,
    )
    outcome_code = models.CharField(max_length=80, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    channel_metadata = models.JSONField(default=dict, blank=True)
    subject = models.CharField(max_length=250)
    notes = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    owner_membership_public_id = models.UUIDField()
    created_by_public_id = models.UUIDField()
    location = models.JSONField(default=dict, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_activity"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(customer__isnull=False)
                | models.Q(contact__isnull=False)
                | models.Q(lead__isnull=False)
                | models.Q(opportunity__isnull=False),
                name="crm_activity_parent_req_v2",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "owner_membership_public_id", "scheduled_for"],
                name="crm_activity_owner_idx",
            ),
            models.Index(
                fields=["company", "owner_membership_public_id", "follow_up_at"],
                name="crm_act_owner_follow_idx",
            ),
            models.Index(
                fields=["company", "status", "scheduled_for"],
                name="crm_activity_due_idx",
            ),
            models.Index(
                fields=["company", "priority", "scheduled_for"],
                name="crm_activity_priority_idx",
            ),
            models.Index(
                fields=["company", "contact", "created_at"],
                name="crm_activity_contact_idx",
            ),
            models.Index(
                fields=["company", "contact", "status", "scheduled_for"],
                name="crm_act_contact_due_idx",
            ),
            models.Index(
                fields=["company", "contact", "status", "follow_up_at"],
                name="crm_act_contact_follow_idx",
            ),
        ]


class ActivityAttachment(TenantOwnedModel):
    class AttachmentKind(models.TextChoices):
        DOCUMENT = "document", "Document"
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        OTHER = "other", "Other"

    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file_object_public_id = models.UUIDField()
    attachment_kind = models.CharField(
        max_length=30,
        choices=AttachmentKind.choices,
        default=AttachmentKind.DOCUMENT,
    )
    caption = models.CharField(max_length=500, blank=True)
    created_by_public_id = models.UUIDField()

    class Meta:
        db_table = "crm_activity_attachment"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "activity", "file_object_public_id"],
                name="crm_act_attach_file_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "activity", "created_at"],
                name="crm_act_attach_activity_idx",
            )
        ]


class StageHistory(TenantOwnedModel):
    entity_type = models.CharField(max_length=30, choices=PipelineStage.EntityType.choices)
    entity_public_id = models.UUIDField()
    from_stage_code = models.CharField(max_length=80, blank=True)
    to_stage_code = models.CharField(max_length=80)
    changed_by_public_id = models.UUIDField()
    changed_at = models.DateTimeField()
    reason_code = models.CharField(max_length=100, blank=True)
    entity_version = models.PositiveBigIntegerField()

    class Meta:
        db_table = "crm_stage_history"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entity_type", "entity_public_id", "entity_version"],
                name="crm_stage_hist_version_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "entity_type", "entity_public_id", "changed_at"],
                name="crm_stage_hist_lookup_idx",
            )
        ]


class ConversionSnapshot(TenantOwnedModel):
    lead = models.OneToOneField(Lead, on_delete=models.PROTECT, related_name="conversion_snapshot")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT)
    source_version = models.PositiveBigIntegerField()
    snapshot = models.JSONField(default=dict)
    converted_by_public_id = models.UUIDField()
    converted_at = models.DateTimeField()

    class Meta:
        db_table = "crm_conversion_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "lead"],
                name="crm_conversion_lead_uq",
            )
        ]


class CrmAutomationRule(TenantOwnedModel):
    class TriggerCode(models.TextChoices):
        CONTACT_CREATED = "contact.created", "Contact created"
        LEAD_CREATED = "lead.created", "Lead created"
        LEAD_STAGE_CHANGED = "lead.stage_changed", "Lead stage changed"
        OPPORTUNITY_CREATED = "opportunity.created", "Opportunity created"
        OPPORTUNITY_STAGE_CHANGED = "opportunity.stage_changed", "Opportunity stage changed"
        ACTIVITY_COMPLETED = "activity.completed", "Activity completed"

    code = models.CharField(max_length=80)
    name = models.CharField(max_length=180)
    description = models.CharField(max_length=500, blank=True)
    trigger_code = models.CharField(max_length=50, choices=TriggerCode.choices)
    condition_tree = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    priority = models.PositiveIntegerField(default=100)
    stop_on_match = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "crm_automation_rule"
        ordering = ["priority", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="crm_auto_rule_code_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "trigger_code", "is_active", "priority"],
                name="crm_auto_rule_trigger_idx",
            )
        ]


class CrmAutomationExecution(TenantOwnedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    rule = models.ForeignKey(
        CrmAutomationRule,
        on_delete=models.PROTECT,
        related_name="executions",
    )
    trigger_code = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=40)
    entity_public_id = models.UUIDField()
    entity_version = models.PositiveBigIntegerField(default=1)
    event_key = models.CharField(max_length=220)
    status = models.CharField(max_length=20, choices=Status.choices)
    matched = models.BooleanField(default=False)
    trigger_payload = models.JSONField(default=dict, blank=True)
    action_results = models.JSONField(default=list, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=1000, blank=True)
    actor_user_public_id = models.UUIDField(null=True, blank=True)
    actor_membership_public_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_automation_execution"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "rule", "event_key"],
                name="crm_auto_exec_event_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "started_at"],
                name="crm_auto_exec_status_idx",
            ),
            models.Index(
                fields=["company", "entity_type", "entity_public_id"],
                name="crm_auto_exec_entity_idx",
            ),
        ]
