import uuid
from collections.abc import Callable

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from modules.configuration.application.services import (
    create_configuration_draft,
    get_active_configuration,
    publish_configuration_version,
)
from modules.configuration.models import ConfigurationDefinition, ConfigurationVersion
from modules.identity.application.tokens import TokenPair
from modules.identity.models import User
from modules.tenant.models import Company, Membership


@pytest.mark.django_db
def test_published_configuration_is_active_and_immutable(
    company_factory: Callable[..., Company],
) -> None:
    company = company_factory()
    definition = ConfigurationDefinition.objects.create(
        code="test.feature",
        name="Feature",
        schema={
            "type": "object",
            "required": ["enabled"],
            "properties": {"enabled": {"type": "boolean"}},
            "additionalProperties": False,
        },
    )
    actor = uuid.uuid4()
    draft = create_configuration_draft(
        company=company,
        definition=definition,
        payload={"enabled": True},
        effective_from=timezone.now(),
        effective_to=None,
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    published = publish_configuration_version(
        version_public_id=draft.public_id,
        company=company,
        actor_public_id=actor,
        correlation_id=uuid.uuid4(),
    )
    active = get_active_configuration(company=company, definition_code="test.feature")
    assert active is not None
    assert active.public_id == published.public_id
    assert published.checksum

    published.payload = {"enabled": False}
    with pytest.raises(ValidationError, match="immutable"):
        published.save()


@pytest.mark.django_db
def test_configuration_schema_rejects_unknown_fields(
    company_factory: Callable[..., Company],
) -> None:
    definition = ConfigurationDefinition.objects.create(
        code="test.closed-schema",
        name="Closed schema",
        schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        },
    )
    with pytest.raises(ValidationError, match="Unknown configuration fields"):
        create_configuration_draft(
            company=company_factory(),
            definition=definition,
            payload={"name": "valid", "unexpected": True},
            effective_from=timezone.now(),
            effective_to=None,
            actor_public_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )


@pytest.mark.django_db
def test_configuration_api_conceals_other_company_draft(
    api_client: APIClient,
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    permission_grant_factory: Callable[[User, Company, list[str]], Membership],
    token_pair_factory: Callable[[User], TokenPair],
) -> None:
    user = user_factory()
    allowed = company_factory()
    other = company_factory()
    permission_grant_factory(user, allowed, ["configuration.publish"])
    definition = ConfigurationDefinition.objects.create(
        code="test.cross-tenant",
        name="Cross tenant",
        schema={"type": "object"},
    )
    draft = ConfigurationVersion.objects.create(
        company=other,
        definition=definition,
        version=1,
        payload={},
        effective_from=timezone.now(),
        created_by_public_id=uuid.uuid4(),
    )
    pair = token_pair_factory(user)
    response = api_client.post(
        f"/api/v1/configurations/{draft.public_id}/publish",
        {},
        format="json",
        headers={
            "Authorization": f"Bearer {pair.access_token}",
            "X-Company-Id": str(allowed.public_id),
        },
    )
    assert response.status_code == 404
    assert str(other.public_id) not in response.content.decode()
