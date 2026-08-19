from decimal import Decimal

from modules.finance.api.serializers import InvoiceLineSerializer, PaymentCreateSerializer
from modules.integration.api.serializers import ExchangeRateCreateSerializer
from modules.procurement.api.serializers import ReceiptLineSerializer, RequestLineSerializer


def test_decimal_serializer_minimums_use_decimal_instances() -> None:
    fields = [
        ExchangeRateCreateSerializer().fields["rate"],
        InvoiceLineSerializer().fields["quantity"],
        PaymentCreateSerializer().fields["amount"],
        RequestLineSerializer().fields["quantity"],
        ReceiptLineSerializer().fields["quantity_received"],
    ]

    assert all(isinstance(field.min_value, Decimal) for field in fields)
