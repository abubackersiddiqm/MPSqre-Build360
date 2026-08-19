from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.finance.application.services import (
    create_budget,
    create_payment,
    transition_budget,
    transition_payment,
)
from modules.finance.models import (
    CommercialLedgerEntry,
    CommercialStage,
    FinancePolicy,
    FinancialPeriod,
    Invoice,
)
from modules.platform.actors import RequestActor
from modules.projects.models import DeliveryStage, Project


@pytest.fixture
def actor(user_factory, membership_factory, company_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    return (
        company,
        user,
        RequestActor(
            user.public_id, membership.public_id, __import__("uuid").uuid4(), "127.0.0.1", "pytest"
        ),
    )


def stage(company, entity_type, code, outcome, next_codes, initial=False):
    return CommercialStage.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=code.title(),
        outcome=outcome,
        allowed_next_codes=next_codes,
        is_initial=initial,
        effective_from=timezone.now(),
    )


def project(company, user):
    delivery = DeliveryStage.objects.create(
        company=company,
        entity_type=DeliveryStage.EntityType.PROJECT,
        code="active",
        name="Active",
        outcome="active",
        allowed_next_codes=[],
        is_initial=True,
        effective_from=timezone.now(),
    )
    return Project.objects.create(
        company=company,
        code="P-001",
        name="Project",
        stage=delivery,
        manager_membership_public_id=__import__("uuid").uuid4(),
        currency=company.currency,
        approved_budget=0,
    )


@pytest.mark.django_db
def test_budget_approval_posts_append_only_ledger(actor):
    company, user, request_actor = actor
    FinancePolicy.objects.create(company=company, enforce_maker_checker=False)
    stage(company, "budget", "draft", "open", ["approved"], True)
    stage(company, "budget", "approved", "approved", [])
    item = create_budget(
        company=company,
        actor=request_actor,
        project_public_id=project(company, user).public_id,
        code="B1",
        name="Budget",
        currency="INR",
        lines=[{"cost_code": "C1", "description": "Civil", "approved_amount": Decimal("100")}],
    )
    period = FinancialPeriod.objects.create(
        company=company,
        code="2026-07",
        name="July",
        starts_on=date(2026, 7, 1),
        ends_on=date(2026, 7, 31),
    )
    approved = transition_budget(
        company=company,
        actor=request_actor,
        budget_public_id=item.public_id,
        target_code="approved",
        expected_version=1,
        period_public_id=period.public_id,
    )
    assert approved.stage.code == "approved"
    ledger = CommercialLedgerEntry.objects.get(company=company, source_public_id=item.public_id)
    assert ledger.amount == Decimal("100")
    with pytest.raises(ValidationError):
        ledger.save()


@pytest.mark.django_db
def test_locked_period_blocks_payment_posting(actor):
    company, user, request_actor = actor
    FinancePolicy.objects.create(company=company, enforce_maker_checker=False)
    stage(company, "payment", "draft", "open", ["posted"], True)
    stage(company, "payment", "posted", "posted", [])
    invoice_stage = stage(company, "invoice", "posted", "posted", [], True)
    project_obj = project(company, user)
    period = FinancialPeriod.objects.create(
        company=company,
        code="2026-07",
        name="July",
        starts_on=date(2026, 7, 1),
        ends_on=date(2026, 7, 31),
        locked_at=timezone.now(),
    )
    invoice = Invoice.objects.create(
        company=company,
        project=project_obj,
        period=period,
        invoice_number="I1",
        invoice_type="vendor",
        counterparty_name="Vendor",
        stage=invoice_stage,
        currency="INR",
        invoice_date=date(2026, 7, 1),
        due_date=date(2026, 7, 31),
        subtotal=100,
        tax_amount=0,
        retention_amount=0,
        total_amount=100,
        outstanding_amount=100,
        created_by_public_id=user.public_id,
        posted_at=timezone.now(),
    )
    with pytest.raises(ValidationError, match="locked"):
        create_payment(
            company=company,
            actor=request_actor,
            invoice_public_id=invoice.public_id,
            period_public_id=period.public_id,
            payment_number="PAY1",
            payment_type="standard",
            amount=Decimal("50"),
            paid_on=date(2026, 7, 5),
        )


@pytest.mark.django_db
def test_maker_checker_can_block_same_user(actor):
    company, user, request_actor = actor
    FinancePolicy.objects.create(company=company, enforce_maker_checker=True)
    stage(company, "payment", "draft", "open", ["posted"], True)
    stage(company, "payment", "posted", "posted", [])
    invoice_stage = stage(company, "invoice", "posted", "posted", [], True)
    project_obj = project(company, user)
    period = FinancialPeriod.objects.create(
        company=company,
        code="2026-08",
        name="August",
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )
    invoice = Invoice.objects.create(
        company=company,
        project=project_obj,
        period=period,
        invoice_number="I2",
        invoice_type="vendor",
        counterparty_name="Vendor",
        stage=invoice_stage,
        currency="INR",
        invoice_date=date(2026, 8, 1),
        due_date=date(2026, 8, 31),
        subtotal=100,
        tax_amount=0,
        retention_amount=0,
        total_amount=100,
        outstanding_amount=100,
        created_by_public_id=user.public_id,
        posted_at=timezone.now(),
    )
    payment = create_payment(
        company=company,
        actor=request_actor,
        invoice_public_id=invoice.public_id,
        period_public_id=period.public_id,
        payment_number="PAY2",
        payment_type="standard",
        amount=Decimal("50"),
        paid_on=date(2026, 8, 5),
    )
    with pytest.raises(ValidationError, match="different approver"):
        transition_payment(
            company=company,
            actor=request_actor,
            payment_public_id=payment.public_id,
            target_code="posted",
            expected_version=1,
        )
