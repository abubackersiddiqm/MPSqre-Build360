from rest_framework import serializers

from modules.crm.models import (
    Activity,
    ActivityAttachment,
    Contact,
    CrmAutomationRule,
    CrmCustomFieldDefinition,
    CrmLeadSource,
    CrmPipeline,
    Customer,
    PipelineStage,
)


class CustomerCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Customer.Kind.choices)
    display_name = serializers.CharField(max_length=250)
    legal_name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    external_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    source_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    custom_fields = serializers.JSONField(required=False)


class ContactCreateSerializer(serializers.Serializer):
    customer_public_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField(max_length=120)
    last_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=160, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    alternate_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    consent_status = serializers.ChoiceField(
        choices=Contact.ConsentStatus.choices,
        required=False,
    )
    preferred_channel_code = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
    )
    address = serializers.JSONField(required=False)
    source_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    custom_fields = serializers.JSONField(required=False)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("At least one protected contact endpoint is required")
        return attrs


class ContactToLeadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=250, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    source_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    estimated_value = serializers.DecimalField(max_digits=19, decimal_places=4, required=False, allow_null=True)
    next_follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    pipeline_public_id = serializers.UUIDField(required=False, allow_null=True)



class LeadCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=250)
    primary_contact_public_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    source_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    customer_public_id = serializers.UUIDField(required=False, allow_null=True)
    customer_display_name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    contact_first_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    contact_last_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    contact_alternate_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    estimated_value = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    next_follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    stage_public_id = serializers.UUIDField(required=False, allow_null=True)
    pipeline_public_id = serializers.UUIDField(required=False, allow_null=True)
    custom_fields = serializers.JSONField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if attrs.get("primary_contact_public_id"):
            return attrs
        if not str(attrs.get("contact_first_name") or "").strip():
            raise serializers.ValidationError({"contact_first_name": "Person name is required when creating a new lead."})
        if not str(attrs.get("contact_phone") or "").strip():
            raise serializers.ValidationError({"contact_phone": "Primary phone number is required when creating a new lead."})
        return attrs


class StageTransitionSerializer(serializers.Serializer):
    target_stage_public_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    reason_code = serializers.CharField(max_length=100, required=False, allow_blank=True)


class LeadConversionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    customer_display_name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    opportunity_name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    expected_close_date = serializers.DateField(required=False, allow_null=True)


class OpportunityProjectConversionSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=80, required=False, allow_blank=True)
    name = serializers.CharField(max_length=250, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    planned_start_date = serializers.DateField(required=False, allow_null=True)
    planned_end_date = serializers.DateField(required=False, allow_null=True)
    location = serializers.JSONField(required=False)


class OpportunityCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=250)
    customer_public_id = serializers.UUIDField()
    primary_contact_public_id = serializers.UUIDField(required=False, allow_null=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=19, decimal_places=4, required=False)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    expected_close_date = serializers.DateField(required=False, allow_null=True)
    stage_public_id = serializers.UUIDField(required=False, allow_null=True)
    pipeline_public_id = serializers.UUIDField(required=False, allow_null=True)
    custom_fields = serializers.JSONField(required=False)


class ActivityCreateSerializer(serializers.Serializer):
    activity_type = serializers.ChoiceField(choices=Activity.ActivityType.choices)
    status = serializers.ChoiceField(choices=Activity.Status.choices, required=False)
    direction = serializers.ChoiceField(choices=Activity.Direction.choices, required=False)
    outcome_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    duration_seconds = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    channel_metadata = serializers.JSONField(required=False, default=dict)
    subject = serializers.CharField(max_length=250)
    notes = serializers.CharField(required=False, allow_blank=True)
    customer_public_id = serializers.UUIDField(required=False, allow_null=True)
    contact_public_id = serializers.UUIDField(required=False, allow_null=True)
    lead_public_id = serializers.UUIDField(required=False, allow_null=True)
    opportunity_public_id = serializers.UUIDField(required=False, allow_null=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=Activity.Priority.choices, required=False)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    location = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        parent_keys = (
            "customer_public_id",
            "contact_public_id",
            "lead_public_id",
            "opportunity_public_id",
        )
        if not any(attrs.get(key) for key in parent_keys):
            raise serializers.ValidationError("An activity must reference a CRM record")
        if attrs.get("activity_type") == "site_visit" and not attrs.get("location"):
            raise serializers.ValidationError(
                {"location": "Location is required for site visits."}
            )
        return attrs


class ActivityUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=Activity.Status.choices, required=False)
    direction = serializers.ChoiceField(choices=Activity.Direction.choices, required=False)
    outcome_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    duration_seconds = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=Activity.Priority.choices, required=False)
    channel_metadata = serializers.JSONField(required=False)


class ActivityAttachmentCreateSerializer(serializers.Serializer):
    file_public_id = serializers.UUIDField()
    attachment_kind = serializers.ChoiceField(choices=ActivityAttachment.AttachmentKind.choices)
    caption = serializers.CharField(max_length=500, required=False, allow_blank=True)



class ContactRevealSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(
        choices=("crm_call", "crm_whatsapp", "crm_email"),
    )


class PipelineStageCreateSerializer(serializers.Serializer):
    pipeline_public_id = serializers.UUIDField(required=False, allow_null=True)
    entity_type = serializers.ChoiceField(choices=PipelineStage.EntityType.choices)
    code = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=160)
    outcome = serializers.ChoiceField(choices=PipelineStage.Outcome.choices)
    sort_order = serializers.IntegerField(min_value=0)
    probability_percent = serializers.IntegerField(min_value=0, max_value=100)
    allowed_next_codes = serializers.ListField(
        child=serializers.SlugField(max_length=80),
        required=False,
    )
    is_initial = serializers.BooleanField(required=False)
    allows_conversion = serializers.BooleanField(required=False)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)



class LeadAIOverrideSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    action_label = serializers.CharField(max_length=300, required=False, allow_blank=True)
    action_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    suggested_due_at = serializers.DateTimeField(required=False, allow_null=True)
    clear_override = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs.get("clear_override"):
            return attrs
        if not any(
            str(attrs.get(key) or "").strip()
            for key in ("summary", "action_label", "action_reason")
        ) and attrs.get("suggested_due_at") is None:
            raise serializers.ValidationError("Provide an override value or set clear_override=true.")
        return attrs


class CrmIndustryPackApplySerializer(serializers.Serializer):
    pack_code = serializers.CharField(max_length=80)


class CrmTerminologyUpdateSerializer(serializers.Serializer):
    terminology = serializers.DictField(child=serializers.CharField(max_length=80))


class CrmPipelineCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=CrmPipeline.EntityType.choices)
    code = serializers.RegexField(regex=r"^[a-z][a-z0-9_-]{0,79}$", max_length=80)
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_default = serializers.BooleanField(required=False, default=False)


class CrmCustomFieldCreateSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=CrmCustomFieldDefinition.EntityType.choices)
    code = serializers.CharField(max_length=80)
    label = serializers.CharField(max_length=160)
    field_type = serializers.ChoiceField(choices=CrmCustomFieldDefinition.FieldType.choices)
    help_text = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_required = serializers.BooleanField(required=False, default=False)
    options = serializers.ListField(child=serializers.CharField(max_length=160), required=False)
    sort_order = serializers.IntegerField(min_value=0, required=False, default=100)


class CrmLeadSourceCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=160)
    channel_type = serializers.ChoiceField(choices=CrmLeadSource.ChannelType.choices)
    sort_order = serializers.IntegerField(min_value=0, required=False, default=100)


class CrmAutomationRuleCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(regex=r"^[a-z][a-z0-9_-]{0,79}$", max_length=80)
    name = serializers.CharField(max_length=180)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    trigger_code = serializers.ChoiceField(choices=CrmAutomationRule.TriggerCode.choices)
    condition_tree = serializers.JSONField(required=False, default=dict)
    actions = serializers.JSONField()
    priority = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=100)
    stop_on_match = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)


class CrmAutomationRuleUpdateSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=180, required=False)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    trigger_code = serializers.ChoiceField(choices=CrmAutomationRule.TriggerCode.choices, required=False)
    condition_tree = serializers.JSONField(required=False)
    actions = serializers.JSONField(required=False)
    priority = serializers.IntegerField(min_value=0, max_value=10000, required=False)
    stop_on_match = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
