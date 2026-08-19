from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from modules.procurement.models import GoodsReceiptLine, VendorQuote


class ProcurementContractTests(SimpleTestCase):
    def test_quote_total_is_controlled(self):
        quote = VendorQuote(
            subtotal=Decimal("100"),
            tax_amount=Decimal("18"),
            freight_amount=Decimal("5"),
            total_amount=Decimal("120"),
        )
        with self.assertRaises(ValidationError):
            quote.clean()

    def test_receipt_quantities_balance(self):
        line = GoodsReceiptLine(
            quantity_received=Decimal("10"),
            quantity_accepted=Decimal("8"),
            quantity_rejected=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            line.clean()
