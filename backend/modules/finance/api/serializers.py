from decimal import Decimal

from rest_framework import serializers


class PeriodCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=30)
    name = serializers.CharField(max_length=120)
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()


class PeriodLockSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=250)


class BudgetLineSerializer(serializers.Serializer):
    cost_code = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=500)
    approved_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0)
    committed_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)
    actual_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)
    accrued_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)
    forecast_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False)


class BudgetCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    code = serializers.CharField(max_length=80)
    name = serializers.CharField(max_length=250)
    currency = serializers.CharField(max_length=3, required=False)
    lines = BudgetLineSerializer(many=True, allow_empty=False)


class TransitionSerializer(serializers.Serializer):
    target_code = serializers.CharField(max_length=50)
    expected_version = serializers.IntegerField(min_value=1)
    period_public_id = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=250, required=False, allow_blank=True)


class VariationCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    variation_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    variation_type = serializers.ChoiceField(choices=["client", "vendor", "internal"])
    currency = serializers.CharField(max_length=3, required=False)
    amount_ex_tax = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0)
    tax_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)
    reason = serializers.CharField(required=False, allow_blank=True)


class InvoiceLineSerializer(serializers.Serializer):
    cost_code = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=500)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0.0001"))
    unit_rate = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0)
    tax_rate_percent = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=0, max_value=100, required=False, default=0)


class InvoiceCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    period_public_id = serializers.UUIDField()
    invoice_number = serializers.CharField(max_length=80)
    invoice_type = serializers.ChoiceField(choices=["client", "vendor"])
    counterparty_name = serializers.CharField(max_length=250)
    counterparty_reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    currency = serializers.CharField(max_length=3, required=False)
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    retention_amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)
    lines = InvoiceLineSerializer(many=True, allow_empty=False)


class PaymentCreateSerializer(serializers.Serializer):
    invoice_public_id = serializers.UUIDField()
    period_public_id = serializers.UUIDField()
    payment_number = serializers.CharField(max_length=80)
    payment_type = serializers.ChoiceField(choices=["standard", "retention_release"], required=False, default="standard")
    amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0.0001"))
    paid_on = serializers.DateField()
    reference = serializers.CharField(max_length=160, required=False, allow_blank=True)


class FinancePolicySerializer(serializers.Serializer):
    enforce_maker_checker = serializers.BooleanField(required=False)
    allow_backdated_posting = serializers.BooleanField(required=False)
    default_retention_percent = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=0, max_value=100, required=False)
    tax_configuration = serializers.JSONField(required=False)


class AdjustmentCreateSerializer(serializers.Serializer):
    project_public_id = serializers.UUIDField()
    period_public_id = serializers.UUIDField()
    posting_number = serializers.CharField(max_length=80)
    entry_type = serializers.ChoiceField(choices=["commitment", "actual", "accrual", "forecast"])
    cost_code = serializers.CharField(max_length=80)
    amount = serializers.DecimalField(max_digits=20, decimal_places=4)
    currency = serializers.CharField(max_length=3, required=False)
    description = serializers.CharField(max_length=500)
