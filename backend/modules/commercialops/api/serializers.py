from decimal import Decimal

from rest_framework import serializers

from modules.commercialops.models import (
    CommercialApproval,
    CommercialClaim,
    CommercialContract,
    CommercialPolicyVersion,
    CommercialRisk,
    ContractMilestone,
    ExtensionOfTime,
    PaymentApplication,
    VariationOrder,
)

NON_NEGATIVE = Decimal("0")


class CommercialPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommercialPolicyVersion
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


class CommercialContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommercialContract
        fields = (
            "public_id",
            "contract_number",
            "project_public_id",
            "parent_contract_public_id",
            "counterparty_public_id",
            "counterparty_name",
            "contract_type_code",
            "procurement_route_code",
            "title",
            "status_code",
            "currency_code",
            "original_value",
            "approved_variation_value",
            "current_contract_value",
            "retention_percent",
            "start_date",
            "planned_completion_date",
            "actual_completion_date",
            "owner_membership_public_id",
            "attributes",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "public_id",
            "status_code",
            "approved_variation_value",
            "current_contract_value",
            "version",
            "created_at",
            "updated_at",
        )


class CommercialContractCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_number = serializers.CharField(max_length=120)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    parent_contract_public_id = serializers.UUIDField(required=False, allow_null=True)
    counterparty_public_id = serializers.UUIDField(required=False, allow_null=True)
    counterparty_name = serializers.CharField(max_length=250)
    contract_type_code = serializers.CharField(max_length=100)
    procurement_route_code = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    title = serializers.CharField(max_length=300)
    currency_code = serializers.CharField(max_length=3)
    original_value = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE
    )
    retention_percent = serializers.DecimalField(
        max_digits=7,
        decimal_places=4,
        min_value=NON_NEGATIVE,
        max_value=Decimal("100"),
        required=False,
        default=NON_NEGATIVE,
    )
    start_date = serializers.DateField()
    planned_completion_date = serializers.DateField()
    actual_completion_date = serializers.DateField(required=False, allow_null=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    attributes = serializers.JSONField(required=False, default=dict)


class ContractMilestoneSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)

    class Meta:
        model = ContractMilestone
        fields = (
            "public_id",
            "contract_number",
            "milestone_number",
            "title",
            "status_code",
            "due_date",
            "achieved_at",
            "currency_code",
            "milestone_value",
            "weight_percent",
            "version",
            "created_at",
            "updated_at",
        )


class ContractMilestoneCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField()
    milestone_number = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=300)
    due_date = serializers.DateField()
    currency_code = serializers.CharField(max_length=3)
    milestone_value = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE, required=False, default=NON_NEGATIVE
    )
    weight_percent = serializers.DecimalField(
        max_digits=7,
        decimal_places=4,
        min_value=NON_NEGATIVE,
        max_value=Decimal("100"),
        required=False,
        default=NON_NEGATIVE,
    )
    evidence_reference = serializers.CharField(
        max_length=500, required=False, allow_blank=True
    )


class VariationOrderSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)

    class Meta:
        model = VariationOrder
        fields = (
            "public_id",
            "contract_number",
            "variation_number",
            "title",
            "reason_code",
            "status_code",
            "currency_code",
            "submitted_value",
            "approved_value",
            "time_impact_days",
            "submitted_at",
            "decision_due_at",
            "decided_at",
            "description",
            "version",
            "created_at",
            "updated_at",
        )


class VariationOrderCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField()
    variation_number = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=300)
    reason_code = serializers.CharField(max_length=100)
    currency_code = serializers.CharField(max_length=3)
    submitted_value = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE
    )
    approved_value = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=NON_NEGATIVE,
        required=False,
        allow_null=True,
    )
    time_impact_days = serializers.IntegerField(required=False, default=0)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)
    decision_due_at = serializers.DateTimeField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)


class PaymentApplicationSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)

    class Meta:
        model = PaymentApplication
        fields = (
            "public_id",
            "contract_number",
            "application_number",
            "period_start",
            "period_end",
            "status_code",
            "currency_code",
            "gross_claimed",
            "certified_amount",
            "retention_amount",
            "deduction_amount",
            "net_payable",
            "submitted_at",
            "certification_due_at",
            "certified_at",
            "description",
            "version",
            "created_at",
            "updated_at",
        )


class PaymentApplicationCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField()
    application_number = serializers.CharField(max_length=120)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    currency_code = serializers.CharField(max_length=3)
    gross_claimed = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE
    )
    certified_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=NON_NEGATIVE,
        required=False,
        allow_null=True,
    )
    retention_amount = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE, required=False, default=NON_NEGATIVE
    )
    deduction_amount = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE, required=False, default=NON_NEGATIVE
    )
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)
    certification_due_at = serializers.DateTimeField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)


class CommercialClaimSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)

    class Meta:
        model = CommercialClaim
        fields = (
            "public_id",
            "contract_number",
            "claim_number",
            "claim_type_code",
            "priority_code",
            "cause_code",
            "title",
            "status_code",
            "currency_code",
            "claimed_amount",
            "assessed_amount",
            "event_date",
            "notice_date",
            "response_due_at",
            "resolved_at",
            "version",
            "created_at",
            "updated_at",
        )


class CommercialClaimCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField()
    claim_number = serializers.CharField(max_length=120)
    claim_type_code = serializers.CharField(max_length=100)
    priority_code = serializers.CharField(max_length=80)
    cause_code = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=300)
    currency_code = serializers.CharField(max_length=3)
    claimed_amount = serializers.DecimalField(
        max_digits=20, decimal_places=2, min_value=NON_NEGATIVE
    )
    assessed_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=NON_NEGATIVE,
        required=False,
        allow_null=True,
    )
    event_date = serializers.DateField()
    notice_date = serializers.DateField(required=False, allow_null=True)
    response_due_at = serializers.DateTimeField(required=False, allow_null=True)
    claimant_party_public_id = serializers.UUIDField(required=False, allow_null=True)
    owner_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)


class ExtensionOfTimeSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)
    claim_number = serializers.CharField(source="claim.claim_number", read_only=True)

    class Meta:
        model = ExtensionOfTime
        fields = (
            "public_id",
            "contract_number",
            "claim_number",
            "eot_number",
            "reason_code",
            "status_code",
            "requested_days",
            "assessed_days",
            "approved_days",
            "impact_start_date",
            "impact_end_date",
            "submitted_at",
            "decision_due_at",
            "decided_at",
            "version",
            "created_at",
            "updated_at",
        )


class ExtensionOfTimeCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField()
    claim_public_id = serializers.UUIDField(required=False, allow_null=True)
    eot_number = serializers.CharField(max_length=120)
    reason_code = serializers.CharField(max_length=100)
    requested_days = serializers.IntegerField(min_value=0)
    assessed_days = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    approved_days = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    impact_start_date = serializers.DateField(required=False, allow_null=True)
    impact_end_date = serializers.DateField(required=False, allow_null=True)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)
    decision_due_at = serializers.DateTimeField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)


class CommercialApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommercialApproval
        fields = (
            "public_id",
            "entity_type_code",
            "entity_public_id",
            "step_code",
            "status_code",
            "requested_by_membership_public_id",
            "approver_membership_public_id",
            "requested_at",
            "due_at",
            "decided_at",
            "decision_code",
            "reason",
            "version",
            "created_at",
            "updated_at",
        )


class CommercialApprovalCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    entity_type_code = serializers.CharField(max_length=100)
    entity_public_id = serializers.UUIDField()
    step_code = serializers.CharField(max_length=100)
    approver_membership_public_id = serializers.UUIDField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class ApprovalDecisionSerializer(serializers.Serializer):
    decision_code = serializers.CharField(max_length=80)
    reason = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1, required=False)


class CommercialRiskSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source="contract.contract_number", read_only=True)

    class Meta:
        model = CommercialRisk
        fields = (
            "public_id",
            "contract_number",
            "linked_entity_type_code",
            "linked_entity_public_id",
            "risk_code",
            "severity_code",
            "status_code",
            "message",
            "due_at",
            "assigned_membership_public_id",
            "resolved_at",
            "resolution_note",
            "version",
            "created_at",
            "updated_at",
        )


class CommercialRiskCreateSerializer(serializers.Serializer):
    policy_public_id = serializers.UUIDField()
    contract_public_id = serializers.UUIDField(required=False, allow_null=True)
    linked_entity_type_code = serializers.CharField(max_length=100)
    linked_entity_public_id = serializers.UUIDField(required=False, allow_null=True)
    risk_code = serializers.CharField(max_length=100)
    severity_code = serializers.CharField(max_length=80)
    message = serializers.CharField()
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    assigned_membership_public_id = serializers.UUIDField(required=False, allow_null=True)


class ResolveRiskSerializer(serializers.Serializer):
    resolution_note = serializers.CharField()
    expected_version = serializers.IntegerField(min_value=1, required=False)


class TransitionSerializer(serializers.Serializer):
    target_status_code = serializers.CharField(max_length=80)
    expected_version = serializers.IntegerField(min_value=1, required=False)
