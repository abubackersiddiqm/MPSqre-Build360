from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.successops.models import AdoptionSnapshot, SubscriptionInvoice, SupportSlaPolicy


@pytest.mark.django_db
def test_invoice_total_must_match(company_factory, user_factory, membership_factory):
    from modules.successops.models import CustomerSuccessAccount

    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)

    account = CustomerSuccessAccount.objects.create(
        company=company,
        code="TEST",
        display_name="Test account",
        segment=CustomerSuccessAccount.Segment.PILOT,
        status=CustomerSuccessAccount.Status.ACTIVE,
        account_owner=membership,
        customer_since=timezone.localdate(),
        health_score=50,
    )
    invoice = SubscriptionInvoice(
        company=company,
        account=account,
        invoice_number="INV-TEST",
        period_start=timezone.localdate(),
        period_end=timezone.localdate(),
        currency="INR",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        total_amount=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
    )
    with pytest.raises(ValidationError):
        invoice.full_clean()


def test_support_sla_escalates_before_resolution():
    policy = SupportSlaPolicy(
        first_response_minutes=60,
        resolution_minutes=120,
        escalation_minutes=180,
    )
    with pytest.raises(ValidationError):
        policy.clean()


def test_adoption_snapshot_company_reverse_accessor_is_isolated():
    from modules.pilotops.models import AdoptionSnapshot as PilotAdoptionSnapshot

    pilot_accessor = (
        PilotAdoptionSnapshot._meta.get_field("company").remote_field.get_accessor_name()
    )
    success_accessor = AdoptionSnapshot._meta.get_field(
        "company"
    ).remote_field.get_accessor_name()

    assert pilot_accessor == "adoptionsnapshot_set"
    assert success_accessor == "customer_success_adoption_snapshots"
    assert pilot_accessor != success_accessor
