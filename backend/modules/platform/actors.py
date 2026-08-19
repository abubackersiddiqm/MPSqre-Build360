import uuid
from dataclasses import dataclass

from rest_framework.request import Request

from modules.platform.audit import request_metadata
from modules.tenant.application.context import TenantContext


@dataclass(frozen=True, slots=True)
class RequestActor:
    user_public_id: uuid.UUID
    membership_public_id: uuid.UUID
    request_id: uuid.UUID
    ip_address: str | None
    user_agent: str


def request_actor(request: Request, tenant_context: TenantContext) -> RequestActor:
    request_id, ip_address, user_agent = request_metadata(request)
    return RequestActor(
        user_public_id=tenant_context.principal.user.public_id,
        membership_public_id=tenant_context.membership.public_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
