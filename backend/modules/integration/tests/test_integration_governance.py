import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.integration.application.services import (
    complete_synchronization_run,
    create_connector,
    create_localization_pack,
    issue_api_client,
    publish_localization_pack,
    record_exchange_rate,
    rotate_api_client,
    start_synchronization_run,
)
from modules.integration.models import ConnectorProfile, ExchangeRateSnapshot, LocalizationPack
from modules.platform.actors import RequestActor


@pytest.fixture
def integration_context(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    return {
        "company": company,
        "actor": RequestActor(
            user_public_id=user.public_id,
            membership_public_id=membership.public_id,
            request_id=uuid.uuid4(),
            ip_address="127.0.0.1",
            user_agent="pytest",
        ),
    }


@pytest.mark.django_db
def test_localization_publication_creates_checksum(integration_context):
    item = create_localization_pack(
        company=integration_context["company"],
        actor=integration_context["actor"],
        code="UAE_EN",
        name="UAE English",
        country_code="AE",
        locale="en-AE",
        currency="AED",
        timezone_code="Asia/Dubai",
        unit_system_code="metric",
        date_format="DD/MM/YYYY",
        time_format="24h",
        number_format={"decimal": ".", "group": ","},
        address_schema={"fields": ["city", "emirate"]},
        tax_schema={"system": "VAT"},
        terminology={"postal_code": "Postal code"},
        effective_from=timezone.now(),
    )
    published = publish_localization_pack(
        company=integration_context["company"],
        actor=integration_context["actor"],
        public_id=item.public_id,
        expected_version=item.version,
    )
    assert published.status == LocalizationPack.Status.PUBLISHED
    assert len(published.checksum_sha256) == 64


@pytest.mark.django_db
def test_exchange_rates_are_append_only(integration_context):
    item = record_exchange_rate(
        company=integration_context["company"],
        actor=integration_context["actor"],
        base_currency="INR",
        quote_currency="USD",
        rate=Decimal("0.01200000"),
        effective_at=timezone.now(),
        source_code="TEST",
    )
    item.rate = Decimal("0.01300000")
    with pytest.raises(ValidationError, match="append-only"):
        item.save()
    assert ExchangeRateSnapshot.objects.count() == 1


@pytest.mark.django_db
def test_api_secret_is_returned_once_and_rotated(integration_context):
    item, secret = issue_api_client(
        company=integration_context["company"],
        actor=integration_context["actor"],
        name="Reporting client",
        scopes=["reporting.read"],
    )
    assert secret
    assert secret not in item.secret_digest_sha256
    rotated, new_secret = rotate_api_client(
        company=integration_context["company"],
        actor=integration_context["actor"],
        public_id=item.public_id,
        expected_version=item.version,
    )
    assert new_secret != secret
    assert rotated.version == 2


@pytest.mark.django_db
def test_sync_is_idempotent_and_terminal_once(integration_context):
    connector = create_connector(
        company=integration_context["company"],
        actor=integration_context["actor"],
        code="LOCAL_ANALYTICS",
        name="Local analytics",
        connector_type=ConnectorProfile.ConnectorType.ANALYTICS,
        provider_code="LOCAL",
        direction=ConnectorProfile.Direction.OUTBOUND,
    )
    first = start_synchronization_run(
        company=integration_context["company"],
        actor=integration_context["actor"],
        connector_public_id=connector.public_id,
        direction=ConnectorProfile.Direction.OUTBOUND,
        idempotency_key="sync-1",
    )
    second = start_synchronization_run(
        company=integration_context["company"],
        actor=integration_context["actor"],
        connector_public_id=connector.public_id,
        direction=ConnectorProfile.Direction.OUTBOUND,
        idempotency_key="sync-1",
    )
    assert first.public_id == second.public_id
    completed = complete_synchronization_run(
        company=integration_context["company"],
        actor=integration_context["actor"],
        public_id=first.public_id,
        expected_version=first.version,
        status="COMPLETED",
        records_read=10,
        records_written=10,
        records_rejected=0,
    )
    with pytest.raises(ValidationError, match="terminal"):
        complete_synchronization_run(
            company=integration_context["company"],
            actor=integration_context["actor"],
            public_id=completed.public_id,
            expected_version=completed.version,
            status="COMPLETED",
            records_read=10,
            records_written=10,
            records_rejected=0,
        )
