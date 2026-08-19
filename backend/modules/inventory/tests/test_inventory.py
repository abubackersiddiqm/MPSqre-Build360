from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from modules.inventory.models import StockLedgerEntry


class LedgerContractTests(SimpleTestCase):
    def test_ledger_is_append_only(self):
        entry = StockLedgerEntry(id=1)
        with self.assertRaises(ValidationError):
            entry.save()
