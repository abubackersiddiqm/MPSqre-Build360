from __future__ import annotations

import uuid

from celery import shared_task

from modules.integration.application.meta_leads import process_meta_lead_receipt


@shared_task(name="integration.process_meta_lead_receipt")
def process_meta_lead_receipt_task(receipt_public_id: str) -> dict[str, str]:
    receipt = process_meta_lead_receipt(uuid.UUID(receipt_public_id))
    return {"public_id": str(receipt.public_id), "status": receipt.status}
