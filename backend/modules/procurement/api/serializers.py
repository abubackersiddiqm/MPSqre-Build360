from decimal import Decimal

from rest_framework import serializers


class RequestLineSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField(required=False, allow_null=True)
    item_code = serializers.CharField(max_length=80, required=False, allow_blank=True)
    description = serializers.CharField(max_length=500)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0.0001"))
    unit_code = serializers.CharField(max_length=30)
    estimated_unit_rate = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False, default=0)


class PurchaseRequestCreateSerializer(serializers.Serializer):
    request_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True)
    project_public_id = serializers.UUIDField(required=False, allow_null=True)
    required_by_date = serializers.DateField(required=False, allow_null=True)
    delivery_location = serializers.JSONField(required=False)
    currency = serializers.CharField(max_length=3, required=False)
    lines = RequestLineSerializer(many=True, allow_empty=False)


class RequestTransitionSerializer(serializers.Serializer):
    target_code = serializers.CharField(max_length=50)
    expected_version = serializers.IntegerField(min_value=1)


class RfqCreateSerializer(serializers.Serializer):
    purchase_request_public_id = serializers.UUIDField()
    rfq_number = serializers.CharField(max_length=80)
    title = serializers.CharField(max_length=250)
    vendor_public_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    close_at = serializers.DateTimeField(required=False, allow_null=True)


class QuoteCreateSerializer(serializers.Serializer):
    rfq_public_id = serializers.UUIDField()
    vendor_public_id = serializers.UUIDField()
    quote_number = serializers.CharField(max_length=80)
    subtotal = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0)
    tax_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0, required=False, default=0)
    freight_amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0, required=False, default=0)
    valid_until = serializers.DateField(required=False, allow_null=True)


class AwardQuoteSerializer(serializers.Serializer):
    po_number = serializers.CharField(max_length=80)


class ReceiptLineSerializer(serializers.Serializer):
    purchase_order_line_public_id = serializers.UUIDField()
    quantity_received = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal("0.0001"))
    quantity_accepted = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=0, required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReceiptCreateSerializer(serializers.Serializer):
    purchase_order_public_id = serializers.UUIDField()
    warehouse_public_id = serializers.UUIDField()
    receipt_number = serializers.CharField(max_length=80)
    lines = ReceiptLineSerializer(many=True, allow_empty=False)


class ReceiptPostSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
