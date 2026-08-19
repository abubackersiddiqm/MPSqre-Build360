from decimal import Decimal

from rest_framework import serializers


class PartnerOrganizationSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    legal_name = serializers.CharField(max_length=250)
    display_name = serializers.CharField(max_length=250)
    organization_type_code = serializers.ChoiceField(choices=["VENDOR", "SUBCONTRACTOR", "CLIENT", "CONSULTANT", "OTHER"])
    registration_number = serializers.CharField(max_length=120, required=False, allow_blank=True)
    tax_registration_number = serializers.CharField(max_length=120, required=False, allow_blank=True)
    country_code = serializers.CharField(max_length=2, required=False, allow_blank=True)
    primary_email = serializers.EmailField(required=False, allow_blank=True)
    primary_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    risk_rating_code = serializers.CharField(max_length=30, required=False, default="UNASSESSED")


class PartnerContactInviteSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=40, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    can_approve = serializers.BooleanField(required=False, default=False)
    is_primary = serializers.BooleanField(required=False, default=False)


class ProjectGrantSerializer(serializers.Serializer):
    contact_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    site_public_id = serializers.UUIDField(required=False, allow_null=True)
    scopes = serializers.ListField(child=serializers.CharField(max_length=50), allow_empty=False)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)


class CollaborationItemSerializer(serializers.Serializer):
    organization_public_id = serializers.UUIDField()
    project_public_id = serializers.UUIDField()
    site_public_id = serializers.UUIDField(required=False, allow_null=True)
    assigned_contact_public_id = serializers.UUIDField(required=False, allow_null=True)
    reference = serializers.CharField(max_length=100)
    item_type_code = serializers.ChoiceField(
        choices=["RFQ", "SUBMITTAL", "DOCUMENT_REVIEW", "APPROVAL", "INVOICE", "CLAIM", "MEETING_ACTION", "GENERAL"]
    )
    title = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    status_code = serializers.CharField(max_length=40, required=False, default="ISSUED")
    priority_code = serializers.ChoiceField(choices=["LOW", "NORMAL", "HIGH", "CRITICAL"], required=False, default="NORMAL")
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    response_required = serializers.BooleanField(required=False, default=True)
    approval_required = serializers.BooleanField(required=False, default=False)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0"))
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    source_module = serializers.CharField(max_length=50, required=False, allow_blank=True)
    source_public_id = serializers.UUIDField(required=False, allow_null=True)


class SubmissionSerializer(serializers.Serializer):
    summary = serializers.CharField(required=False, allow_blank=True)
    data = serializers.JSONField(required=False, default=dict)
    attachment_references = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class DecisionSerializer(serializers.Serializer):
    submission_public_id = serializers.UUIDField(required=False, allow_null=True)
    decision_code = serializers.ChoiceField(choices=["APPROVED", "REJECTED", "REVISION_REQUIRED", "ACKNOWLEDGED"])
    notes = serializers.CharField(required=False, allow_blank=True)


class MessageSerializer(serializers.Serializer):
    body = serializers.CharField()
    attachment_references = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    is_internal = serializers.BooleanField(required=False, default=False)
