from __future__ import annotations

from typing import Any

from rest_framework import serializers

from modules.payrollops.models import PayrollPeriod, PayrollPolicyVersion, PayrollRun


class PayrollPolicySerializer(serializers.ModelSerializer[PayrollPolicyVersion]):
    public_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PayrollPolicyVersion
        fields = [
            "public_id",
            "code",
            "name",
            "version",
            "status_code",
            "locale_code",
            "currency",
            "effective_from",
            "effective_to",
            "published_at",
            "retired_at",
            "configuration",
            "change_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_configuration(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be an object")
        if not str(value.get("initial_run_status", "")).strip():
            raise serializers.ValidationError("initial_run_status is required")
        transitions = value.get("transitions")
        if not isinstance(transitions, list):
            raise serializers.ValidationError("transitions must be a list")
        for index, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                raise serializers.ValidationError(
                    f"Transition {index + 1} must be an object"
                )
            for key in ("from", "to", "permission"):
                if not str(transition.get(key, "")).strip():
                    raise serializers.ValidationError(
                        f"Transition {index + 1} requires {key}"
                    )
        return value


class PayrollPeriodCreateSerializer(serializers.Serializer[dict[str, Any]]):
    code = serializers.CharField(max_length=80)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    payment_due_on = serializers.DateField()
    status_code = serializers.CharField(max_length=80)
    configuration = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError("ends_on cannot be before starts_on")
        if attrs["payment_due_on"] < attrs["ends_on"]:
            raise serializers.ValidationError(
                "payment_due_on cannot be before ends_on"
            )
        return attrs


class PayrollPeriodSerializer(serializers.ModelSerializer[PayrollPeriod]):
    public_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = [
            "public_id",
            "code",
            "starts_on",
            "ends_on",
            "payment_due_on",
            "status_code",
            "lock_version",
            "configuration",
            "created_at",
            "updated_at",
        ]


class PayrollRunCreateSerializer(serializers.Serializer[dict[str, Any]]):
    period_public_id = serializers.UUIDField()
    policy_public_id = serializers.UUIDField()
    run_number = serializers.IntegerField(min_value=1)
    run_type_code = serializers.CharField(max_length=80)
    metadata = serializers.JSONField(required=False, default=dict)


class PayrollRunSerializer(serializers.ModelSerializer[PayrollRun]):
    public_id = serializers.UUIDField(read_only=True)
    period_public_id = serializers.UUIDField(source="period.public_id", read_only=True)
    period_code = serializers.CharField(source="period.code", read_only=True)
    policy_public_id = serializers.UUIDField(source="policy.public_id", read_only=True)
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "public_id",
            "period_public_id",
            "period_code",
            "policy_public_id",
            "policy_code",
            "policy_version",
            "run_number",
            "run_type_code",
            "status_code",
            "currency",
            "version",
            "calculated_at",
            "approved_at",
            "approved_by_public_id",
            "locked_at",
            "gross_amount",
            "deduction_amount",
            "employer_cost_amount",
            "net_amount",
            "employee_count",
            "exception_count",
            "metadata",
            "created_at",
            "updated_at",
        ]


class PayrollRunTransitionSerializer(serializers.Serializer[dict[str, Any]]):
    expected_version = serializers.IntegerField(min_value=1)
    target_status_code = serializers.CharField(max_length=80)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class PayrollLineSerializer(serializers.Serializer[dict[str, Any]]):
    employee_public_id = serializers.UUIDField()
    employment_public_id = serializers.UUIDField(required=False, allow_null=True)
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=0)
    deduction_amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=0,
    )
    employer_cost_amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=0,
    )
    status_code = serializers.CharField(max_length=80)
    exception_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    component_breakdown = serializers.ListField(required=False, default=list)
    calculation_trace = serializers.JSONField(required=False, default=dict)
    source_reference = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["deduction_amount"] > attrs["gross_amount"]:
            raise serializers.ValidationError("Deductions cannot exceed gross amount")
        return attrs


class PayrollLinesUpsertSerializer(serializers.Serializer[dict[str, Any]]):
    expected_version = serializers.IntegerField(min_value=1)
    lines = PayrollLineSerializer(many=True, allow_empty=False)


class ApprovalRequestSerializer(serializers.Serializer[dict[str, Any]]):
    run_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    status_code = serializers.CharField(max_length=80)
    requested_from_membership_public_id = serializers.UUIDField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class ApprovalDecisionSerializer(serializers.Serializer[dict[str, Any]]):
    decision_code = serializers.CharField(max_length=80)
    status_code = serializers.CharField(max_length=80)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ExceptionResolutionSerializer(serializers.Serializer[dict[str, Any]]):
    status_code = serializers.CharField(max_length=80)
    resolution_note = serializers.CharField(max_length=500)
