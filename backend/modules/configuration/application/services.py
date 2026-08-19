from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.configuration.models import ConfigurationDefinition, ConfigurationVersion
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company


def canonical_checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _matches_type(value: object, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, int | float) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def validate_payload(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    expected = schema.get("type", "object")
    if not isinstance(expected, str) or not _matches_type(payload, expected):
        raise ValidationError("Configuration payload does not match its declared type")
    required = schema.get("required", [])
    if isinstance(required, list):
        missing = [name for name in required if isinstance(name, str) and name not in payload]
        if missing:
            raise ValidationError(f"Configuration payload is missing: {', '.join(missing)}")
    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for name, rules in properties.items():
            if name not in payload or not isinstance(rules, dict):
                continue
            field_type = rules.get("type")
            if isinstance(field_type, str) and not _matches_type(payload[name], field_type):
                raise ValidationError(f"Configuration field {name} has an invalid type")
    if schema.get("additionalProperties") is False and isinstance(properties, dict):
        unknown = sorted(set(payload) - set(properties))
        if unknown:
            raise ValidationError(f"Unknown configuration fields: {', '.join(unknown)}")


@transaction.atomic
def create_configuration_draft(
    *,
    company: Company,
    definition: ConfigurationDefinition,
    payload: dict[str, Any],
    effective_from: datetime,
    effective_to: datetime | None,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ConfigurationVersion:
    validate_payload(definition.schema, payload)
    current = (
        ConfigurationVersion.objects.select_for_update()
        .filter(company=company, definition=definition)
        .order_by("-version")
        .first()
    )
    version = 1 if current is None else current.version + 1
    draft = ConfigurationVersion.objects.create(
        company=company,
        definition=definition,
        version=version,
        payload=payload,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by_public_id=actor_public_id,
    )
    append_audit(
        AuditRecord(
            action="configuration.version.created",
            entity_type="configuration_version",
            entity_public_id=draft.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={"definition_code": definition.code, "version": version},
        )
    )
    return draft


@transaction.atomic
def publish_configuration_version(
    *,
    version_public_id: uuid.UUID,
    company: Company,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> ConfigurationVersion:
    version = (
        ConfigurationVersion.objects.select_for_update()
        .select_related("definition")
        .filter(public_id=version_public_id, company=company)
        .first()
    )
    if not version:
        raise ValidationError("Configuration version was not found")
    if version.status != ConfigurationVersion.Status.DRAFT:
        raise ValidationError("Only draft configuration versions can be published")
    validate_payload(version.definition.schema, version.payload)
    version.status = ConfigurationVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.checksum = canonical_checksum(version.payload)
    version.full_clean()
    version.save(update_fields=["status", "published_at", "checksum", "updated_at"])
    append_audit(
        AuditRecord(
            action="configuration.version.published",
            entity_type="configuration_version",
            entity_public_id=version.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "definition_code": version.definition.code,
                "version": version.version,
                "checksum": version.checksum,
            },
        )
    )
    append_event(
        EventRecord(
            event_type="configuration.version_published",
            aggregate_type="configuration",
            aggregate_public_id=version.public_id,
            aggregate_version=version.version,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload={"definition_code": version.definition.code},
        )
    )
    return version


def get_active_configuration(
    *,
    company: Company,
    definition_code: str,
    at: datetime | None = None,
) -> ConfigurationVersion | None:
    moment = at or timezone.now()
    return (
        ConfigurationVersion.objects.select_related("definition")
        .filter(
            company=company,
            definition__code=definition_code,
            definition__is_active=True,
            status=ConfigurationVersion.Status.PUBLISHED,
            effective_from__lte=moment,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=moment))
        .order_by("-effective_from", "-version")
        .first()
    )


def list_active_configurations(*, company: Company) -> list[ConfigurationVersion]:
    definitions = ConfigurationDefinition.objects.filter(is_active=True).order_by("code")
    active: list[ConfigurationVersion] = []
    for definition in definitions:
        version = get_active_configuration(company=company, definition_code=definition.code)
        if version:
            active.append(version)
    return active
