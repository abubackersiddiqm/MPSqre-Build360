from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.crm.models import Activity, Contact, Lead
from modules.integration.application.meta_leads import (
    create_meta_connector,
    process_meta_lead_receipt,
    record_webhook_payload,
    verify_webhook_signature,
)
from modules.integration.models import ConnectorProfile, MetaLeadReceipt
from modules.platform.actors import RequestActor
from modules.subscription.models import EntitlementOverride

pytestmark = pytest.mark.django_db


def _actor(user, membership):
    return RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address=None,
        user_agent="pytest",
    )


def _enable_meta(company):
    EntitlementOverride.objects.create(
        company=company,
        entitlement_code="crm.meta_ads",
        enabled=True,
        effective_from=timezone.now(),
        reason_code="test",
        set_by_public_id=company.public_id,
    )



def test_meta_connector_stores_secret_reference_not_raw_secret(
    company_factory,
    user_factory,
    membership_factory,
    monkeypatch,
):
    company = company_factory()
    _enable_meta(company)
    user = user_factory(email="meta-admin@example.com")
    membership = membership_factory(user, company)
    monkeypatch.setenv(
        "META_TEST_SECRET",
        json.dumps({"page_access_token": "PAGE_TOKEN", "app_secret": "APP_SECRET"}),
    )
    connector, verify_token = create_meta_connector(
        company=company,
        actor=_actor(user, membership),
        code="META_LEADS",
        name="Meta Leads",
        page_id="12345",
        page_name="Test Page",
        lead_form_ids=["F1"],
        graph_api_version="v99.0",
        default_owner_membership_public_id=membership.public_id,
        secret_ref="env://META_TEST_SECRET",
    )
    assert connector.secret_ref == "env://META_TEST_SECRET"  # noqa: S105 -- secret reference, not secret material
    assert "PAGE_TOKEN" not in json.dumps(connector.public_config)
    assert "APP_SECRET" not in json.dumps(connector.public_config)
    assert verify_token not in json.dumps(connector.public_config)


def test_meta_webhook_signature_uses_app_secret(
    company_factory,
    user_factory,
    membership_factory,
    monkeypatch,
):
    company = company_factory()
    _enable_meta(company)
    user = user_factory(email="meta-sign@example.com")
    membership = membership_factory(user, company)
    monkeypatch.setenv(
        "META_SIGNATURE_SECRET",
        json.dumps({"page_access_token": "PAGE_TOKEN", "app_secret": "APP_SECRET"}),
    )
    connector, _ = create_meta_connector(
        company=company,
        actor=_actor(user, membership),
        code="META_SIGN",
        name="Meta Sign",
        page_id="12345",
        page_name="",
        lead_form_ids=[],
        graph_api_version="v99.0",
        default_owner_membership_public_id=membership.public_id,
        secret_ref="env://META_SIGNATURE_SECRET",
    )
    connector.status = ConnectorProfile.Status.ACTIVE
    connector.save(update_fields=["status", "updated_at"])
    body = b'{"object":"page"}'
    signature = "sha256=" + hmac.new(b"APP_SECRET", body, hashlib.sha256).hexdigest()
    verify_webhook_signature(connector=connector, raw_body=body, signature=signature)
    with pytest.raises(ValidationError):
        verify_webhook_signature(
            connector=connector,
            raw_body=body,
            signature="sha256=" + "0" * 64,
        )


def test_webhook_receipt_is_idempotent(company_factory, user_factory, membership_factory):
    company = company_factory()
    _enable_meta(company)
    user = user_factory(email="meta-idempotent@example.com")
    membership = membership_factory(user, company)
    connector, _ = create_meta_connector(
        company=company,
        actor=_actor(user, membership),
        code="META_IDEMP",
        name="Meta Idempotent",
        page_id="PAGE1",
        page_name="",
        lead_form_ids=["FORM1"],
        graph_api_version="v99.0",
        default_owner_membership_public_id=membership.public_id,
        secret_ref="env://META_IDEMP_SECRET",
    )
    connector.status = ConnectorProfile.Status.ACTIVE
    connector.save(update_fields=["status", "updated_at"])
    payload = {
        "object": "page",
        "entry": [{
            "id": "PAGE1",
            "changes": [{
                "field": "leadgen",
                "value": {
                    "leadgen_id": "LEAD-1",
                    "page_id": "PAGE1",
                    "form_id": "FORM1",
                    "ad_id": "AD1",
                },
            }],
        }],
    }
    first = record_webhook_payload(connector=connector, payload=payload)
    second = record_webhook_payload(connector=connector, payload=payload)
    assert len(first) == 1
    assert second == []
    assert MetaLeadReceipt.objects.filter(connector=connector, external_lead_id="LEAD-1").count() == 1



def test_process_meta_lead_creates_people_call_action_without_automatic_lead(
    company_factory,
    user_factory,
    membership_factory,
    monkeypatch,
):
    company = company_factory()
    _enable_meta(company)
    user = user_factory(email="meta-process@example.com")
    membership = membership_factory(user, company)
    monkeypatch.setenv(
        "META_PROCESS_SECRET",
        json.dumps({"page_access_token": "PAGE_TOKEN", "app_secret": "APP_SECRET"}),
    )
    connector, _ = create_meta_connector(
        company=company,
        actor=_actor(user, membership),
        code="META_PROCESS",
        name="Meta Process",
        page_id="PAGE1",
        page_name="",
        lead_form_ids=["FORM1"],
        graph_api_version="v99.0",
        default_owner_membership_public_id=membership.public_id,
        secret_ref="env://META_PROCESS_SECRET",
    )
    connector.status = ConnectorProfile.Status.ACTIVE
    connector.save(update_fields=["status", "updated_at"])
    receipt = MetaLeadReceipt.objects.create(
        company=company,
        connector=connector,
        external_lead_id="META-LEAD-100",
        page_id="PAGE1",
        form_id="FORM1",
        payload_digest_sha256="a" * 64,
    )
    fetched = {
        "created_time": "2026-08-13T06:00:00+00:00",
        "form_id": "FORM1",
        "ad_id": "AD1",
        "ad_name": "Chennai Construction Enquiry",
        "adset_id": "AS1",
        "adset_name": "Chennai 25-45",
        "campaign_id": "C1",
        "campaign_name": "Chennai House Construction",
        "platform": "ig",
        "field_data": [
            {"name": "full_name", "values": ["Example Buyer"]},
            {"name": "email", "values": ["buyer@example.com"]},
            {"name": "phone_number", "values": ["+919999999999"]},
            {"name": "budget", "values": ["40-50 Lakh"]},
            {"name": "requirement", "values": ["G+1 House Construction"]},
        ],
    }
    with patch("modules.integration.application.meta_leads._graph_json", return_value=fetched):
        first = process_meta_lead_receipt(receipt.public_id)

    assert first.status == MetaLeadReceipt.Status.PROCESSED, first.error_summary
    assert first.contact_public_id is not None
    assert first.lead_public_id is None
    assert Lead.objects.filter(company=company).count() == 0

    contact = Contact.objects.get(public_id=first.contact_public_id)
    assert contact.source_code == "INSTAGRAM"
    assert "meta-ads" in contact.tags
    assert "meta-source:instagram" in contact.tags
    assert "meta_ads" not in contact.custom_fields

    call = Activity.objects.get(company=company, contact=contact, activity_type=Activity.ActivityType.CALL)
    assert call.status == Activity.Status.PLANNED
    assert call.direction == Activity.Direction.OUTBOUND
    assert call.priority == Activity.Priority.HIGH
    assert "New Instagram enquiry" in call.subject
    assert call.channel_metadata["provider"] == "meta_lead_ads"
    assert call.channel_metadata["source_code"] == "INSTAGRAM"
    assert call.channel_metadata["campaign_name"] == "Chennai House Construction"
    assert call.channel_metadata["submitted_answers"]["budget"] == "40-50 Lakh"
    assert "email" not in call.channel_metadata["submitted_answers"]
    assert "phone_number" not in call.channel_metadata["submitted_answers"]

    second_receipt = MetaLeadReceipt.objects.create(
        company=company,
        connector=connector,
        external_lead_id="META-LEAD-101",
        page_id="PAGE1",
        form_id="FORM1",
        payload_digest_sha256="b" * 64,
    )
    fetched_facebook = {**fetched, "platform": "fb", "ad_id": "AD2", "ad_name": "Facebook Retargeting"}
    with patch("modules.integration.application.meta_leads._graph_json", return_value=fetched_facebook):
        second = process_meta_lead_receipt(second_receipt.public_id)

    assert second.status == MetaLeadReceipt.Status.DUPLICATE
    assert second.contact_public_id == first.contact_public_id
    assert second.lead_public_id is None
    assert Lead.objects.filter(company=company).count() == 0
    contact.refresh_from_db()
    assert contact.source_code == "FACEBOOK"
    assert Activity.objects.filter(company=company, contact=contact, activity_type=Activity.ActivityType.CALL).count() == 2

