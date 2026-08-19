from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.vendor.models import VendorQualification


class VendorModelTests(TestCase):
    def test_score_must_be_bounded(self):
        qualification = VendorQualification(score=Decimal("101"))
        with self.assertRaises(ValidationError):
            qualification.clean()
