from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError

from modules.crm.models import Customer, Opportunity
from modules.tenant.models import Company


def validate_customer_reference(company: Company, public_id: uuid.UUID | None) -> None:
    if public_id is None:
        return
    if not Customer.objects.filter(company=company, public_id=public_id).exists():
        raise ValidationError("Customer reference was not found for this company")


def validate_opportunity_reference(company: Company, public_id: uuid.UUID | None) -> None:
    if public_id is None:
        return
    if not Opportunity.objects.filter(company=company, public_id=public_id).exists():
        raise ValidationError("Opportunity reference was not found for this company")
