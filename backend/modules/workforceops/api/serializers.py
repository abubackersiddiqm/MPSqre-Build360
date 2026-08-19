from decimal import Decimal

from rest_framework import serializers

from modules.workforceops.models import (
    EmployeeSkillCredential,
    SkillDefinition,
    WorkforceDemand,
    WorkforcePlan,
    WorkforcePolicyVersion,
)


class WorkforcePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkforcePolicyVersion
        fields = (
            "public_id",
            "code",
            "name",
            "version",
            "status_code",
            "effective_from",
            "effective_to",
            "published_at",
            "retired_at",
            "configuration",
            "change_note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("public_id", "created_at", "updated_at")


class SkillDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillDefinition
        fields = (
            "public_id",
            "code",
            "name",
            "version",
            "category_code",
            "description",
            "proficiency_scale",
            "is_certification",
            "default_validity_days",
            "effective_from",
            "effective_to",
            "is_active",
            "configuration",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("public_id", "created_at", "updated_at")


class WorkforcePlanSerializer(serializers.ModelSerializer):
    policy_code = serializers.CharField(source="policy.code", read_only=True)
    policy_version = serializers.IntegerField(source="policy.version", read_only=True)

    class Meta:
        model = WorkforcePlan
        fields = (
            "public_id",
            "policy_code",
            "policy_version",
            "code",
            "name",
            "starts_on",
            "ends_on",
            "status_code",
            "version",
            "owner_membership_public_id",
            "approved_at",
            "approved_by_public_id",
            "locked_at",
            "notes",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WorkforcePlanCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=200)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError("ends_on cannot be before starts_on")
        return attrs


class WorkforceDemandSerializer(serializers.ModelSerializer):
    plan_public_id = serializers.UUIDField(source="plan.public_id", read_only=True)
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    open_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = WorkforceDemand
        fields = (
            "public_id",
            "plan_public_id",
            "plan_code",
            "demand_code",
            "project_public_id",
            "location_public_id",
            "cost_center_code",
            "role_code",
            "employment_type_code",
            "priority_code",
            "status_code",
            "quantity_required",
            "quantity_filled",
            "open_quantity",
            "starts_on",
            "ends_on",
            "estimated_cost",
            "currency",
            "skill_requirements",
            "configuration",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WorkforceDemandCreateSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    demand_code = serializers.CharField(max_length=100)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    location_public_id = serializers.UUIDField(required=False, allow_null=True)
    cost_center_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    role_code = serializers.CharField(max_length=100)
    employment_type_code = serializers.CharField(
        max_length=80, required=False, allow_blank=True
    )
    priority_code = serializers.CharField(max_length=80)
    status_code = serializers.CharField(max_length=80)
    quantity_required = serializers.IntegerField(min_value=1)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    estimated_cost = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
        min_value=0,
        default=0,
    )
    currency = serializers.CharField(max_length=3)
    skill_requirements = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    configuration = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        if attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError("ends_on cannot be before starts_on")
        return attrs


class WorkforcePlanTransitionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    target_status_code = serializers.CharField(max_length=80)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class WorkforceAssignmentCreateSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    assignment_status_code = serializers.CharField(max_length=80)
    allocation_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=100,
    )
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(required=False, allow_null=True)
    source_reference = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    metadata = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs.get("ends_on") and attrs["ends_on"] < attrs["starts_on"]:
            raise serializers.ValidationError("ends_on cannot be before starts_on")
        return attrs


class CredentialSerializer(serializers.ModelSerializer):
    skill_public_id = serializers.UUIDField(source="skill.public_id", read_only=True)
    skill_code = serializers.CharField(source="skill.code", read_only=True)
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = EmployeeSkillCredential
        fields = (
            "public_id",
            "employee_public_id",
            "skill_public_id",
            "skill_code",
            "skill_name",
            "proficiency_code",
            "credential_reference",
            "issued_on",
            "expires_on",
            "verification_status_code",
            "verified_at",
            "verified_by_public_id",
            "metadata",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CredentialUpsertSerializer(serializers.Serializer):
    employee_public_id = serializers.UUIDField()
    skill_public_id = serializers.UUIDField()
    proficiency_code = serializers.CharField(max_length=80)
    credential_reference = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    issued_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)
    verification_status_code = serializers.CharField(max_length=80)
    verified_at = serializers.DateTimeField(required=False, allow_null=True)
    verified_by_public_id = serializers.UUIDField(required=False, allow_null=True)
    evidence_object_key = serializers.CharField(
        max_length=500, required=False, allow_blank=True
    )
    metadata = serializers.DictField(required=False)

    def validate(self, attrs):
        if (
            attrs.get("issued_on")
            and attrs.get("expires_on")
            and attrs["expires_on"] < attrs["issued_on"]
        ):
            raise serializers.ValidationError("expires_on cannot be before issued_on")
        return attrs


class ApprovalRequestSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    requested_from_membership_public_id = serializers.UUIDField()
    status_code = serializers.CharField(max_length=80)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False)


class ApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RiskCreateSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField(required=False, allow_null=True)
    demand_public_id = serializers.UUIDField(required=False, allow_null=True)
    employee_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    status_code = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=1000)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    assigned_to_membership_public_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    metadata = serializers.DictField(required=False)

    def validate(self, attrs):
        if not any(
            attrs.get(field)
            for field in ("plan_public_id", "demand_public_id", "employee_public_id")
        ):
            raise serializers.ValidationError("A risk subject is required")
        return attrs


class RiskResolutionSerializer(serializers.Serializer):
    status_code = serializers.CharField(max_length=80)
    resolution_note = serializers.CharField(max_length=1000)
