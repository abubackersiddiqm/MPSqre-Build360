import uuid

import pytest

from modules.communication.models import CommunicationChannel
from modules.notifications.application.services import (
    create_notification,
    mark_read,
    upsert_preference,
)
from modules.notifications.models import Notification, NotificationDelivery
from modules.platform.actors import RequestActor


@pytest.fixture
def notification_actor(company_factory, user_factory, membership_factory):
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
def test_notification_is_tenant_and_user_scoped(notification_actor):
    company, user, actor = notification_actor
    notification = create_notification(
        company=company,
        actor=actor,
        user_public_id=user.public_id,
        event_code="test.created",
        title="Created",
        body="A governed notification was created.",
    )
    delivery = NotificationDelivery.objects.get(notification=notification)
    assert delivery.channel == CommunicationChannel.IN_APP
    assert delivery.status == NotificationDelivery.Status.DELIVERED
    read = mark_read(
        company=company,
        actor=actor,
        notification_public_id=notification.public_id,
    )
    assert read.read_at is not None


@pytest.mark.django_db
def test_muted_preference_suppresses_in_app_delivery(notification_actor):
    company, user, actor = notification_actor
    upsert_preference(
        company=company,
        actor=actor,
        event_code="test.muted",
        channel=CommunicationChannel.IN_APP,
        enabled=False,
        digest_mode="muted",
    )
    notification = create_notification(
        company=company,
        actor=actor,
        user_public_id=user.public_id,
        event_code="test.muted",
        title="Muted",
        body="This should be suppressed by preference.",
    )
    delivery = NotificationDelivery.objects.get(notification=notification)
    assert delivery.status == NotificationDelivery.Status.SUPPRESSED
    assert Notification.objects.filter(company=company, public_id=notification.public_id).exists()
