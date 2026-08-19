from decimal import Decimal

from rest_framework import serializers

from modules.successops.models import SupportSlaPolicy, SupportTicket


class SupportTicketCreateSerializer(serializers.Serializer):
    account_public_id = serializers.UUIDField()
    subject = serializers.CharField(max_length=240)
    description = serializers.CharField(max_length=2000)
    category = serializers.CharField(max_length=100, default="general")
    severity = serializers.ChoiceField(choices=SupportSlaPolicy.Severity.choices)
    assigned_membership_public_id = serializers.UUIDField(required=False, allow_null=True)


class SupportTicketTransitionSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=SupportTicket.Status.choices)
    expected_version = serializers.IntegerField(min_value=1)
    resolution_summary = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    assigned_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class InvoiceCreateSerializer(serializers.Serializer):
    account_public_id = serializers.UUIDField()
    invoice_number = serializers.CharField(max_length=100)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    currency = serializers.CharField(max_length=3)
    subtotal = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
    )
    tax_amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        default=Decimal("0"),
    )
    external_reference = serializers.CharField(max_length=240, required=False, allow_blank=True)


class InvoiceIssueSerializer(serializers.Serializer):
    issued_on = serializers.DateField()
    due_on = serializers.DateField()
    expected_version = serializers.IntegerField(min_value=1)


class PaymentCreateSerializer(serializers.Serializer):
    invoice_public_id = serializers.UUIDField()
    reference = serializers.CharField(max_length=140)
    amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    received_at = serializers.DateTimeField()


class SuccessPlanCreateSerializer(serializers.Serializer):
    account_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=240)
    objectives = serializers.ListField(child=serializers.JSONField(), allow_empty=False)
    owner_membership_public_id = serializers.UUIDField()
    next_review_on = serializers.DateField(required=False, allow_null=True)
    renewal_on = serializers.DateField(required=False, allow_null=True)


class AdoptionSnapshotSerializer(serializers.Serializer):
    captured_on = serializers.DateField()
    active_users = serializers.IntegerField(min_value=0)
    active_projects = serializers.IntegerField(min_value=0)
    support_ticket_count = serializers.IntegerField(min_value=0)
    feature_utilization = serializers.DictField(child=serializers.JSONField())
    adoption_score = serializers.IntegerField(min_value=0, max_value=100)
    engagement_score = serializers.IntegerField(min_value=0, max_value=100)
