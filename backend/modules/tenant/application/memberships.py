import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.identity.models import Role
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Membership, MembershipRole


@transaction.atomic
def assign_role(
    *,
    membership: Membership,
    role: Role,
    assigned_by_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> MembershipRole:
    locked_membership = (
        Membership.objects.select_for_update()
        .select_related("company")
        .get(pk=membership.pk)
    )
    if role.company_public_id != locked_membership.company.public_id:
        raise ValidationError("Role assignment cannot cross companies")
    assignment = MembershipRole(
        membership=locked_membership,
        role_public_id=role.public_id,
        assigned_by_public_id=assigned_by_public_id,
        effective_from=timezone.now(),
    )
    assignment.full_clean()
    assignment.save()
    append_audit(
        AuditRecord(
            action="identity.membership_role.assigned",
            entity_type="membership_role",
            entity_public_id=assignment.public_id,
            actor_public_id=assigned_by_public_id,
            company_public_id=locked_membership.company.public_id,
            request_id=correlation_id,
            correlation_id=correlation_id,
            after={
                "membership_public_id": str(locked_membership.public_id),
                "role_public_id": str(role.public_id),
            },
        )
    )
    append_event(
        EventRecord(
            event_type="identity.membership_role_assigned",
            aggregate_type="membership",
            aggregate_public_id=locked_membership.public_id,
            aggregate_version=1,
            company_public_id=locked_membership.company.public_id,
            correlation_id=correlation_id,
            payload={"role_public_id": str(role.public_id)},
        )
    )
    return assignment

