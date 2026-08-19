import uuid
from datetime import datetime

from django.db import transaction

from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.subscription.models import EntitlementOverride
from modules.tenant.models import Company


@transaction.atomic
def create_entitlement_override(
    *,
    company: Company,
    entitlement_code: str,
    enabled: bool,
    limit_value: int | None,
    effective_from: datetime,
    effective_to: datetime | None,
    reason_code: str,
    actor_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> EntitlementOverride:
    override = EntitlementOverride(
        company=company,
        entitlement_code=entitlement_code,
        enabled=enabled,
        limit_value=limit_value,
        effective_from=effective_from,
        effective_to=effective_to,
        reason_code=reason_code,
        set_by_public_id=actor_public_id,
    )
    override.full_clean()
    override.save()
    append_audit(
        AuditRecord(
            action="subscription.entitlement_override.created",
            entity_type="entitlement_override",
            entity_public_id=override.public_id,
            actor_public_id=actor_public_id,
            company_public_id=company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "entitlement_code": entitlement_code,
                "enabled": enabled,
                "limit_value": limit_value,
                "reason_code": reason_code,
            },
        )
    )
    append_event(
        EventRecord(
            event_type="subscription.entitlement_override_created",
            aggregate_type="entitlement_override",
            aggregate_public_id=override.public_id,
            aggregate_version=1,
            company_public_id=company.public_id,
            correlation_id=correlation_id,
            payload={"entitlement_code": entitlement_code, "enabled": enabled},
        )
    )
    return override
