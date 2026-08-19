from rest_framework import serializers

from modules.controlplane.models import SupportAccessRequest, TenantAccount
from modules.subscription.models import CompanySubscription


class TenantLifecycleSerializer(serializers.Serializer):
    target_status = serializers.ChoiceField(choices=TenantAccount.LifecycleStatus.choices)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)
    grace_until = serializers.DateTimeField(required=False, allow_null=True)


class PlanCreateSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Z0-9][A-Z0-9._-]{1,99}$")
    version = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=200)
    entitlements = serializers.DictField(child=serializers.BooleanField())
    limits = serializers.DictField(child=serializers.IntegerField(min_value=0, allow_null=True))
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(required=False, allow_null=True)


class SubscriptionAssignSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[
            (CompanySubscription.Status.TRIAL, "Trial"),
            (CompanySubscription.Status.ACTIVE, "Active"),
            (CompanySubscription.Status.GRACE, "Grace"),
        ]
    )
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    grace_until = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=500)


class SupportRequestCreateSerializer(serializers.Serializer):
    tenant_public_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=10, max_length=1000)
    scope_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=10,
    )
    duration_hours = serializers.IntegerField(min_value=1, max_value=168)


class SupportDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            (SupportAccessRequest.Status.APPROVED, "Approved"),
            (SupportAccessRequest.Status.REJECTED, "Rejected"),
        ]
    )
    reason = serializers.CharField(max_length=500)
