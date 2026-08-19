import hashlib
import hmac
import json
import uuid

import pytest
from django.core.exceptions import ValidationError

from modules.communication.application.callbacks import process_callback
from modules.communication.application.services import (
    create_request,
    create_template,
    dispatch_request,
    publish_template,
    record_consent,
)
from modules.communication.models import (
    ChannelPolicy,
    CommunicationChannel,
    CommunicationRequest,
    ConsentRecord,
    ProviderConfiguration,
)
from modules.platform.actors import RequestActor


@pytest.fixture
def communication_actor(company_factory, user_factory, membership_factory):
    company = company_factory()
    user = user_factory()
    membership = membership_factory(user, company)
    actor = RequestActor(
        user_public_id=user.public_id,
        membership_public_id=membership.public_id,
        request_id=uuid.uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    return company, user, actor


@pytest.mark.django_db
def test_template_variables_are_declared(communication_actor):
    company, _, actor = communication_actor
    with pytest.raises(ValidationError, match="undeclared"):
        create_template(
            company=company,
            actor=actor,
            code="TEST",
            name="Test",
            channel=CommunicationChannel.IN_APP,
            locale="en-IN",
            subject_template="{title}",
            body_template="Hello {unknown}",
            variable_names=["title"],
            purpose_code="test",
        )


@pytest.mark.django_db
def test_external_request_is_suppressed_without_consent(communication_actor):
    company, user, actor = communication_actor
    ChannelPolicy.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        is_enabled=True,
        consent_required=True,
        timezone=company.timezone,
    )
    ProviderConfiguration.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        code="LOCAL",
        display_name="Local",
        adapter_code="local_noop",
        is_active=True,
    )
    template = create_template(
        company=company,
        actor=actor,
        code="ALERT",
        name="Alert",
        channel=CommunicationChannel.EMAIL,
        locale="en-IN",
        subject_template="{title}",
        body_template="{body}",
        variable_names=["title", "body"],
        purpose_code="service_alert",
    )
    publish_template(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
    )
    request = create_request(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
        subject_type="user",
        subject_public_id=user.public_id,
        recipient_reference_type="user",
        recipient_reference_public_id=user.public_id,
        template_variables={"title": "Alert", "body": "Body"},
        idempotency_key="without-consent",
    )
    assert request.status == CommunicationRequest.Status.SUPPRESSED
    assert request.suppression_reason == "consent_not_granted"


@pytest.mark.django_db
def test_consented_request_dispatches_idempotently(communication_actor):
    company, user, actor = communication_actor
    ChannelPolicy.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        is_enabled=True,
        consent_required=True,
        timezone=company.timezone,
    )
    ProviderConfiguration.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        code="LOCAL",
        display_name="Local",
        adapter_code="local_noop",
        is_active=True,
    )
    template = create_template(
        company=company,
        actor=actor,
        code="SERVICE",
        name="Service",
        channel=CommunicationChannel.EMAIL,
        locale="en-IN",
        subject_template="{title}",
        body_template="{body}",
        variable_names=["title", "body"],
        purpose_code="service",
    )
    publish_template(company=company, actor=actor, template_public_id=template.public_id)
    record_consent(
        company=company,
        actor=actor,
        subject_type="user",
        subject_public_id=user.public_id,
        channel=CommunicationChannel.EMAIL,
        purpose_code="service",
        status=ConsentRecord.Status.GRANTED,
        source_code="test",
    )
    request = create_request(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
        subject_type="user",
        subject_public_id=user.public_id,
        recipient_reference_type="user",
        recipient_reference_public_id=user.public_id,
        template_variables={"title": "Service", "body": "Body"},
        idempotency_key="same-request",
    )
    duplicate = create_request(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
        subject_type="user",
        subject_public_id=user.public_id,
        recipient_reference_type="user",
        recipient_reference_public_id=user.public_id,
        template_variables={"title": "Service", "body": "Body"},
        idempotency_key="same-request",
    )
    assert request.public_id == duplicate.public_id
    sent = dispatch_request(
        company=company,
        actor=actor,
        request_public_id=request.public_id,
    )
    assert sent.status == CommunicationRequest.Status.SENT
    assert sent.attempts.count() == 1


@pytest.mark.django_db
def test_callback_signature_updates_delivery(communication_actor, settings):
    company, user, actor = communication_actor
    settings.COMMUNICATION_CALLBACK_KEYS = {"test": "callback-secret"}
    ChannelPolicy.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        is_enabled=True,
        consent_required=False,
        timezone=company.timezone,
    )
    provider = ProviderConfiguration.objects.create(
        company=company,
        channel=CommunicationChannel.EMAIL,
        code="CALLBACK",
        display_name="Callback",
        adapter_code="local_noop",
        callback_key_id="test",
        is_active=True,
        supports_delivery_receipts=True,
    )
    template = create_template(
        company=company,
        actor=actor,
        code="CALLBACK",
        name="Callback",
        channel=CommunicationChannel.EMAIL,
        locale="en-IN",
        subject_template="{title}",
        body_template="{body}",
        variable_names=["title", "body"],
        purpose_code="callback",
    )
    publish_template(company=company, actor=actor, template_public_id=template.public_id)
    request = create_request(
        company=company,
        actor=actor,
        template_public_id=template.public_id,
        subject_type="user",
        subject_public_id=user.public_id,
        recipient_reference_type="user",
        recipient_reference_public_id=user.public_id,
        template_variables={"title": "Callback", "body": "Body"},
        idempotency_key="callback-request",
    )
    request = dispatch_request(company=company, actor=actor, request_public_id=request.public_id)
    body = json.dumps(
        {
            "event_id": "evt-1",
            "event_type": "delivery",
            "status": "delivered",
            "provider_message_id": request.provider_message_id,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"callback-secret", body, hashlib.sha256).hexdigest()
    receipt = process_callback(
        provider_public_id=provider.public_id,
        raw_body=body,
        signature=signature,
    )
    request.refresh_from_db()
    assert receipt.signature_valid is True
    assert request.status == CommunicationRequest.Status.DELIVERED
