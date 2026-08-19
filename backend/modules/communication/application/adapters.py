from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ValidationError

from modules.communication.models import CommunicationRequest, ProviderConfiguration


@dataclass(frozen=True, slots=True)
class AdapterResult:
    status: str
    provider_message_id: str
    metadata: dict[str, object]
    error_code: str = ""
    error_message: str = ""


class CommunicationAdapter(Protocol):
    def send(
        self,
        *,
        request: CommunicationRequest,
        provider: ProviderConfiguration,
    ) -> AdapterResult: ...


class InAppAdapter:
    def send(
        self,
        *,
        request: CommunicationRequest,
        provider: ProviderConfiguration,
    ) -> AdapterResult:
        return AdapterResult(
            status="delivered",
            provider_message_id=f"in-app:{request.public_id}",
            metadata={"adapter": "in_app"},
        )


class LocalNoopAdapter:
    def send(
        self,
        *,
        request: CommunicationRequest,
        provider: ProviderConfiguration,
    ) -> AdapterResult:
        if not settings.COMMUNICATION_LOCAL_ADAPTER_ENABLED:
            raise ValidationError("The local communication adapter is disabled")
        return AdapterResult(
            status="accepted",
            provider_message_id=f"local:{uuid.uuid4()}",
            metadata={
                "adapter": "local_noop",
                "delivery_simulated": True,
                "channel": request.channel,
            },
        )


_ADAPTERS: dict[str, CommunicationAdapter] = {
    "in_app": InAppAdapter(),
    "local_noop": LocalNoopAdapter(),
}


def resolve_adapter(code: str) -> CommunicationAdapter:
    adapter = _ADAPTERS.get(code)
    if adapter is None:
        raise ValidationError("Communication provider adapter is not registered")
    return adapter
