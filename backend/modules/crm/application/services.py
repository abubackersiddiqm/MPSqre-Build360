from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from modules.crm.application.configuration import default_pipeline, validate_custom_fields
from modules.crm.application.protection import (
    blind_index,
    decrypt_value,
    encrypt_value,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from modules.crm.models import (
    Activity,
    Contact,
    ConversionSnapshot,
    CrmPipeline,
    Customer,
    Lead,
    Opportunity,
    PipelineStage,
    StageHistory,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.tenant.models import Company, Membership


@dataclass(frozen=True, slots=True)
class RequestActor:
    user_public_id: uuid.UUID
    membership_public_id: uuid.UUID
    request_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str = ""


def _assert_membership(company: Company, membership_public_id: uuid.UUID) -> None:
    now = timezone.now()
    active = (
        Membership.objects.filter(
            company=company,
            public_id=membership_public_id,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .exists()
    )
    if not active:
        raise ValidationError("Owner membership is not active for this company")


def _stage(company: Company, public_id: uuid.UUID, entity_type: str) -> PipelineStage:
    stage = PipelineStage.objects.filter(
        company=company,
        public_id=public_id,
        entity_type=entity_type,
        is_active=True,
    ).first()
    if stage is None:
        raise ValidationError("Pipeline stage is not active for this company")
    if stage.pipeline_id is None:
        pipeline = default_pipeline(company, entity_type)
        PipelineStage.objects.filter(pk=stage.pk, pipeline__isnull=True).update(pipeline=pipeline)
        stage.pipeline = pipeline
    return stage


def initial_stage(
    company: Company,
    entity_type: str,
    pipeline_public_id: uuid.UUID | None = None,
) -> PipelineStage:
    if pipeline_public_id:
        pipeline = CrmPipeline.objects.filter(
            company=company, public_id=pipeline_public_id, entity_type=entity_type, is_active=True
        ).first()
        if pipeline is None:
            raise ValidationError("CRM pipeline is not active for this company")
    else:
        pipeline = default_pipeline(company, entity_type)
    PipelineStage.objects.filter(
        company=company, entity_type=entity_type, pipeline__isnull=True
    ).update(pipeline=pipeline)
    stage = PipelineStage.objects.filter(
        company=company,
        pipeline=pipeline,
        entity_type=entity_type,
        is_active=True,
        is_initial=True,
    ).order_by("sort_order").first()
    if stage is None:
        raise ValidationError("An initial CRM pipeline stage has not been configured")
    return stage


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason_code: str = "",
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type=entity_type,
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            before=before or {},
            after=after or {},
            reason_code=reason_code,
        )
    )


def _event(
    *,
    actor: RequestActor,
    company: Company,
    event_type: str,
    aggregate_type: str,
    aggregate_public_id: uuid.UUID,
    aggregate_version: int,
    payload: dict[str, Any],
) -> None:
    append_event(
        EventRecord(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_public_id=aggregate_public_id,
            aggregate_version=aggregate_version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


def _dispatch_automation(
    *,
    company: Company,
    actor: RequestActor,
    trigger_code: str,
    record: Any,
    context: dict[str, Any] | None = None,
) -> None:
    # Local import avoids a services <-> automation module import cycle.
    from modules.crm.application.automation import dispatch_automation_event

    dispatch_automation_event(
        company=company,
        actor=actor,
        trigger_code=trigger_code,
        record=record,
        context=context,
    )


@transaction.atomic
def create_customer(
    *,
    company: Company,
    actor: RequestActor,
    kind: str,
    display_name: str,
    legal_name: str = "",
    external_reference: str = "",
    source_code: str = "",
    owner_membership_public_id: uuid.UUID | None = None,
    notes: str = "",
    custom_fields: dict[str, Any] | None = None,
) -> Customer:
    owner_id = owner_membership_public_id or actor.membership_public_id
    _assert_membership(company, owner_id)
    custom_fields = validate_custom_fields(company=company, entity_type="customer", values=custom_fields)
    customer = Customer(
        company=company,
        kind=kind,
        display_name=display_name.strip(),
        legal_name=legal_name.strip(),
        normalized_name=normalize_name(display_name),
        external_reference=external_reference.strip(),
        source_code=source_code.strip(),
        owner_membership_public_id=owner_id,
        notes=notes.strip(),
        custom_fields=custom_fields,
    )
    customer.full_clean()
    customer.save()
    _audit(
        actor=actor,
        company=company,
        action="crm.customer.created",
        entity_type="crm_customer",
        entity_public_id=customer.public_id,
        after={"kind": customer.kind, "display_name": customer.display_name},
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.customer_created",
        aggregate_type="crm_customer",
        aggregate_public_id=customer.public_id,
        aggregate_version=customer.version,
        payload={"kind": customer.kind},
    )
    return customer


@transaction.atomic
def create_contact(
    *,
    company: Company,
    actor: RequestActor,
    first_name: str,
    last_name: str = "",
    job_title: str = "",
    email: str = "",
    phone: str = "",
    alternate_phone: str = "",
    customer: Customer | None = None,
    consent_status: str = Contact.ConsentStatus.UNKNOWN,
    preferred_channel_code: str = "",
    address: dict[str, Any] | None = None,
    source_code: str = "",
    tags: list[str] | None = None,
    notes: str = "",
    custom_fields: dict[str, Any] | None = None,
    owner_membership_public_id: uuid.UUID | None = None,
    is_primary: bool = False,
) -> Contact:
    if customer is not None and customer.company_id != company.pk:
        raise ValidationError("Contact customer cannot cross companies")
    owner_id = owner_membership_public_id or actor.membership_public_id
    _assert_membership(company, owner_id)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    normalized_alternate_phone = normalize_phone(alternate_phone)
    if normalized_alternate_phone and normalized_alternate_phone == normalized_phone:
        normalized_alternate_phone = ""
    normalized_tags = sorted({str(tag).strip()[:80] for tag in (tags or []) if str(tag).strip()})
    custom_fields = validate_custom_fields(company=company, entity_type="contact", values=custom_fields)
    contact = Contact(
        company=company,
        customer=customer,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        job_title=job_title.strip(),
        email_ciphertext=encrypt_value(normalized_email),
        email_blind_index=blind_index(normalized_email, purpose="email"),
        phone_ciphertext=encrypt_value(normalized_phone),
        phone_blind_index=blind_index(normalized_phone, purpose="phone"),
        alternate_phone_ciphertext=encrypt_value(normalized_alternate_phone),
        alternate_phone_blind_index=blind_index(normalized_alternate_phone, purpose="phone"),
        email_last_four=normalized_email[-4:] if normalized_email else "",
        phone_last_four=normalized_phone[-4:] if normalized_phone else "",
        alternate_phone_last_four=normalized_alternate_phone[-4:] if normalized_alternate_phone else "",
        consent_status=consent_status,
        preferred_channel_code=preferred_channel_code.strip(),
        address=address or {},
        source_code=source_code.strip(),
        tags=normalized_tags,
        notes=notes.strip(),
        custom_fields=custom_fields or {},
        owner_membership_public_id=owner_id,
        is_primary=is_primary,
    )
    contact.full_clean()
    contact.save()
    _audit(
        actor=actor,
        company=company,
        action="crm.contact.created",
        entity_type="crm_contact",
        entity_public_id=contact.public_id,
        after={
            "customer_public_id": str(customer.public_id) if customer else None,
            "has_email": bool(normalized_email),
            "has_phone": bool(normalized_phone),
            "has_alternate_phone": bool(normalized_alternate_phone),
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.contact_created",
        aggregate_type="crm_contact",
        aggregate_public_id=contact.public_id,
        aggregate_version=contact.version,
        payload={"customer_public_id": str(customer.public_id) if customer else None},
    )
    _dispatch_automation(company=company, actor=actor, trigger_code="contact.created", record=contact)
    return contact


def contact_duplicates(
    *,
    company: Company,
    email: str = "",
    phone: str = "",
    alternate_phone: str = "",
) -> QuerySet[Contact]:
    query = Q(pk__in=[])
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)
    normalized_alternate_phone = normalize_phone(alternate_phone)
    if normalized_email:
        query |= Q(email_blind_index=blind_index(normalized_email, purpose="email"))
    for candidate in (normalized_phone, normalized_alternate_phone):
        if candidate:
            candidate_index = blind_index(candidate, purpose="phone")
            query |= Q(phone_blind_index=candidate_index) | Q(alternate_phone_blind_index=candidate_index)
    return Contact.objects.filter(company=company, is_active=True).filter(query)


@transaction.atomic
def reveal_contact(
    *,
    company: Company,
    actor: RequestActor,
    contact_public_id: uuid.UUID,
    reason_code: str,
) -> dict[str, str]:
    reason = reason_code.strip()
    field_by_reason = {
        "crm_call": "phone",
        "crm_whatsapp": "phone",
        "crm_email": "email",
    }
    revealed_field = field_by_reason.get(reason)
    if revealed_field is None:
        raise ValidationError("A supported reveal reason is required")
    contact = Contact.objects.filter(company=company, public_id=contact_public_id).first()
    if contact is None:
        raise ValidationError("Contact was not found")
    revealed_fields = [revealed_field]
    if revealed_field == "phone" and contact.alternate_phone_ciphertext:
        revealed_fields.append("alternate_phone")
    _audit(
        actor=actor,
        company=company,
        action="crm.contact.revealed",
        entity_type="crm_contact",
        entity_public_id=contact.public_id,
        reason_code=reason,
        after={"revealed_fields": revealed_fields},
    )
    if revealed_field == "email":
        return {"email": decrypt_value(contact.email_ciphertext)}
    return {
        "phone": decrypt_value(contact.phone_ciphertext),
        "alternate_phone": decrypt_value(contact.alternate_phone_ciphertext),
    }


@transaction.atomic
def create_or_reuse_lead_from_contact(
    *,
    company: Company,
    actor: RequestActor,
    contact_public_id: uuid.UUID,
    title: str = "",
    description: str = "",
    source_code: str = "",
    estimated_value: Decimal | None = None,
    next_follow_up_at: datetime | None = None,
    pipeline_public_id: uuid.UUID | None = None,
) -> tuple[Lead, bool]:
    contact = (
        Contact.objects.select_for_update(of=("self",))
        .select_related("customer")
        .filter(
            company=company,
            public_id=contact_public_id,
            is_active=True,
        )
        .first()
    )
    if contact is None:
        raise ValidationError("Contact was not found")
    existing = (
        Lead.objects.select_related("stage", "customer", "primary_contact")
        .filter(
            company=company,
            primary_contact=contact,
            converted_at__isnull=True,
            disqualified_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing, False
    display_name = " ".join(part for part in [contact.first_name, contact.last_name] if part).strip()
    lead = create_lead(
        company=company,
        actor=actor,
        title=title.strip() or f"{display_name or 'Contact'} enquiry",
        description=description,
        source_code=source_code.strip() or contact.source_code,
        customer=contact.customer,
        primary_contact=contact,
        owner_membership_public_id=contact.owner_membership_public_id or actor.membership_public_id,
        estimated_value=estimated_value,
        next_follow_up_at=next_follow_up_at,
        pipeline_public_id=pipeline_public_id,
    )
    return lead, True


@transaction.atomic
def create_lead(
    *,
    company: Company,
    actor: RequestActor,
    title: str,
    description: str = "",
    source_code: str = "",
    customer: Customer | None = None,
    primary_contact: Contact | None = None,
    owner_membership_public_id: uuid.UUID | None = None,
    estimated_value: Decimal | None = None,
    currency: str | None = None,
    next_follow_up_at: datetime | None = None,
    stage_public_id: uuid.UUID | None = None,
    pipeline_public_id: uuid.UUID | None = None,
    custom_fields: dict[str, Any] | None = None,
) -> Lead:
    owner_id = owner_membership_public_id or actor.membership_public_id
    _assert_membership(company, owner_id)
    if customer is not None and customer.company_id != company.pk:
        raise ValidationError("Lead customer cannot cross companies")
    if primary_contact is not None and primary_contact.company_id != company.pk:
        raise ValidationError("Lead contact cannot cross companies")
    stage = (
        _stage(company, stage_public_id, PipelineStage.EntityType.LEAD)
        if stage_public_id
        else initial_stage(company, PipelineStage.EntityType.LEAD, pipeline_public_id)
    )
    if pipeline_public_id and stage.pipeline and str(stage.pipeline.public_id) != str(pipeline_public_id):
        raise ValidationError("Lead stage does not belong to the requested pipeline")
    custom_fields = validate_custom_fields(company=company, entity_type="lead", values=custom_fields)
    lead = Lead(
        company=company,
        title=title.strip(),
        description=description.strip(),
        source_code=source_code.strip(),
        stage=stage,
        customer=customer,
        primary_contact=primary_contact,
        owner_membership_public_id=owner_id,
        estimated_value=estimated_value,
        currency=(currency or company.currency).upper(),
        next_follow_up_at=next_follow_up_at,
        custom_fields=custom_fields,
    )
    lead.full_clean()
    lead.save()
    StageHistory.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        entity_public_id=lead.public_id,
        from_stage_code="",
        to_stage_code=stage.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=timezone.now(),
        entity_version=lead.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="crm.lead.created",
        entity_type="crm_lead",
        entity_public_id=lead.public_id,
        after={"stage": stage.code, "source_code": lead.source_code},
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.lead_created",
        aggregate_type="crm_lead",
        aggregate_public_id=lead.public_id,
        aggregate_version=lead.version,
        payload={"stage": stage.code},
    )
    _dispatch_automation(company=company, actor=actor, trigger_code="lead.created", record=lead)
    return lead


@transaction.atomic
def transition_lead(
    *,
    company: Company,
    actor: RequestActor,
    lead_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> Lead:
    lead = Lead.objects.select_for_update().select_related("stage").filter(
        company=company,
        public_id=lead_public_id,
    ).first()
    if lead is None:
        raise ValidationError("Lead was not found")
    if lead.version != expected_version:
        raise ValidationError("Lead has changed; refresh before retrying")
    target = _stage(company, target_stage_public_id, PipelineStage.EntityType.LEAD)
    if target.pipeline_id != lead.stage.pipeline_id:
        raise ValidationError("Lead transitions cannot cross CRM pipelines")
    if target.outcome == PipelineStage.Outcome.CONVERTED:
        raise ValidationError("Use the lead conversion operation for converted stages")
    if target.code not in lead.stage.allowed_next_codes:
        raise ValidationError("The requested lead transition is not permitted")
    before = {"stage": lead.stage.code, "version": lead.version}
    old_code = lead.stage.code
    lead.stage = target
    lead.version += 1
    now = timezone.now()
    if target.outcome == PipelineStage.Outcome.QUALIFIED:
        lead.qualified_at = now
    elif target.outcome == PipelineStage.Outcome.DISQUALIFIED:
        lead.disqualified_at = now
        lead.closed_reason_code = reason_code.strip()
    lead.full_clean()
    lead.save()
    StageHistory.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        entity_public_id=lead.public_id,
        from_stage_code=old_code,
        to_stage_code=target.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=now,
        reason_code=reason_code.strip(),
        entity_version=lead.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="crm.lead.transitioned",
        entity_type="crm_lead",
        entity_public_id=lead.public_id,
        before=before,
        after={"stage": target.code, "version": lead.version},
        reason_code=reason_code.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.lead_stage_changed",
        aggregate_type="crm_lead",
        aggregate_public_id=lead.public_id,
        aggregate_version=lead.version,
        payload={"from_stage": old_code, "to_stage": target.code},
    )
    _dispatch_automation(
        company=company, actor=actor, trigger_code="lead.stage_changed", record=lead,
        context={"from_stage": old_code, "to_stage": target.code},
    )
    return lead


@transaction.atomic
def create_opportunity(
    *,
    company: Company,
    actor: RequestActor,
    name: str,
    customer: Customer,
    primary_contact: Contact | None = None,
    source_lead: Lead | None = None,
    owner_membership_public_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("0"),
    currency: str | None = None,
    expected_close_date: date | None = None,
    stage_public_id: uuid.UUID | None = None,
    pipeline_public_id: uuid.UUID | None = None,
    custom_fields: dict[str, Any] | None = None,
) -> Opportunity:
    owner_id = owner_membership_public_id or actor.membership_public_id
    _assert_membership(company, owner_id)
    if customer.company_id != company.pk:
        raise ValidationError("Opportunity customer cannot cross companies")
    if primary_contact is not None and primary_contact.company_id != company.pk:
        raise ValidationError("Opportunity contact cannot cross companies")
    if source_lead is not None and source_lead.company_id != company.pk:
        raise ValidationError("Opportunity lead cannot cross companies")
    stage = (
        _stage(company, stage_public_id, PipelineStage.EntityType.OPPORTUNITY)
        if stage_public_id
        else initial_stage(company, PipelineStage.EntityType.OPPORTUNITY, pipeline_public_id)
    )
    if pipeline_public_id and stage.pipeline and str(stage.pipeline.public_id) != str(pipeline_public_id):
        raise ValidationError("Opportunity stage does not belong to the requested pipeline")
    custom_fields = validate_custom_fields(company=company, entity_type="opportunity", values=custom_fields)
    opportunity = Opportunity(
        company=company,
        name=name.strip(),
        customer=customer,
        primary_contact=primary_contact,
        source_lead=source_lead,
        stage=stage,
        owner_membership_public_id=owner_id,
        amount=amount,
        currency=(currency or company.currency).upper(),
        expected_close_date=expected_close_date,
        probability_percent=stage.probability_percent,
        custom_fields=custom_fields,
    )
    opportunity.full_clean()
    opportunity.save()
    StageHistory.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        entity_public_id=opportunity.public_id,
        from_stage_code="",
        to_stage_code=stage.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=timezone.now(),
        entity_version=opportunity.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="crm.opportunity.created",
        entity_type="crm_opportunity",
        entity_public_id=opportunity.public_id,
        after={"stage": stage.code, "amount": str(opportunity.amount)},
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.opportunity_created",
        aggregate_type="crm_opportunity",
        aggregate_public_id=opportunity.public_id,
        aggregate_version=opportunity.version,
        payload={"stage": stage.code, "currency": opportunity.currency},
    )
    _dispatch_automation(company=company, actor=actor, trigger_code="opportunity.created", record=opportunity)
    return opportunity


@transaction.atomic
def transition_opportunity(
    *,
    company: Company,
    actor: RequestActor,
    opportunity_public_id: uuid.UUID,
    target_stage_public_id: uuid.UUID,
    expected_version: int,
    reason_code: str = "",
) -> Opportunity:
    opportunity = Opportunity.objects.select_for_update().select_related("stage").filter(
        company=company,
        public_id=opportunity_public_id,
    ).first()
    if opportunity is None:
        raise ValidationError("Opportunity was not found")
    if opportunity.version != expected_version:
        raise ValidationError("Opportunity has changed; refresh before retrying")
    target = _stage(company, target_stage_public_id, PipelineStage.EntityType.OPPORTUNITY)
    if target.pipeline_id != opportunity.stage.pipeline_id:
        raise ValidationError("Opportunity transitions cannot cross CRM pipelines")
    if target.code not in opportunity.stage.allowed_next_codes:
        raise ValidationError("The requested opportunity transition is not permitted")
    old_code = opportunity.stage.code
    before = {"stage": old_code, "version": opportunity.version}
    opportunity.stage = target
    opportunity.probability_percent = target.probability_percent
    opportunity.version += 1
    now = timezone.now()
    if target.outcome == PipelineStage.Outcome.WON:
        opportunity.won_at = now
    elif target.outcome == PipelineStage.Outcome.LOST:
        opportunity.lost_at = now
        opportunity.close_reason_code = reason_code.strip()
    opportunity.full_clean()
    opportunity.save()
    StageHistory.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.OPPORTUNITY,
        entity_public_id=opportunity.public_id,
        from_stage_code=old_code,
        to_stage_code=target.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=now,
        reason_code=reason_code.strip(),
        entity_version=opportunity.version,
    )
    _audit(
        actor=actor,
        company=company,
        action="crm.opportunity.transitioned",
        entity_type="crm_opportunity",
        entity_public_id=opportunity.public_id,
        before=before,
        after={"stage": target.code, "version": opportunity.version},
        reason_code=reason_code.strip(),
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.opportunity_stage_changed",
        aggregate_type="crm_opportunity",
        aggregate_public_id=opportunity.public_id,
        aggregate_version=opportunity.version,
        payload={"from_stage": old_code, "to_stage": target.code},
    )
    _dispatch_automation(
        company=company, actor=actor, trigger_code="opportunity.stage_changed", record=opportunity,
        context={"from_stage": old_code, "to_stage": target.code},
    )
    return opportunity


@transaction.atomic
def convert_lead(
    *,
    company: Company,
    actor: RequestActor,
    lead_public_id: uuid.UUID,
    expected_version: int,
    customer_display_name: str = "",
    opportunity_name: str = "",
    expected_close_date: date | None = None,
) -> ConversionSnapshot:
    lead = Lead.objects.select_for_update(of=("self",)).select_related(
        "stage", "customer", "primary_contact"
    ).filter(company=company, public_id=lead_public_id).first()
    if lead is None:
        raise ValidationError("Lead was not found")
    existing = ConversionSnapshot.objects.select_related("customer", "opportunity").filter(
        company=company,
        lead=lead,
    ).first()
    if existing is not None:
        return existing
    if lead.version != expected_version:
        raise ValidationError("Lead has changed; refresh before retrying")
    if not lead.stage.allows_conversion:
        raise ValidationError("The current lead stage does not allow conversion")
    customer = lead.customer
    if customer is None:
        customer = create_customer(
            company=company,
            actor=actor,
            kind=Customer.Kind.ORGANIZATION,
            display_name=customer_display_name.strip() or lead.title,
            source_code=lead.source_code,
            owner_membership_public_id=lead.owner_membership_public_id,
        )
        lead.customer = customer
        if lead.primary_contact is not None:
            lead.primary_contact.customer = customer
            lead.primary_contact.version += 1
            lead.primary_contact.save(update_fields=["customer", "version", "updated_at"])
    opportunity = create_opportunity(
        company=company,
        actor=actor,
        name=opportunity_name.strip() or lead.title,
        customer=customer,
        primary_contact=lead.primary_contact,
        source_lead=lead,
        owner_membership_public_id=lead.owner_membership_public_id,
        amount=lead.estimated_value or Decimal("0"),
        currency=lead.currency,
        expected_close_date=expected_close_date,
    )
    source_version = lead.version
    conversion_stage = PipelineStage.objects.filter(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        pipeline=lead.stage.pipeline,
        outcome=PipelineStage.Outcome.CONVERTED,
        is_active=True,
    ).order_by("sort_order").first()
    if conversion_stage is None:
        raise ValidationError("A converted lead stage has not been configured")
    if conversion_stage.code not in lead.stage.allowed_next_codes:
        raise ValidationError("The configured lead stage does not allow conversion")
    old_stage_code = lead.stage.code
    lead.stage = conversion_stage
    lead.converted_at = timezone.now()
    lead.version += 1
    lead.save(update_fields=["customer", "stage", "converted_at", "version", "updated_at"])
    StageHistory.objects.create(
        company=company,
        entity_type=PipelineStage.EntityType.LEAD,
        entity_public_id=lead.public_id,
        from_stage_code=old_stage_code,
        to_stage_code=conversion_stage.code,
        changed_by_public_id=actor.user_public_id,
        changed_at=lead.converted_at,
        entity_version=lead.version,
    )
    snapshot_payload = {
        "lead_public_id": str(lead.public_id),
        "lead_title": lead.title,
        "source_code": lead.source_code,
        "source_version": source_version,
        "customer_public_id": str(customer.public_id),
        "opportunity_public_id": str(opportunity.public_id),
        "estimated_value": str(lead.estimated_value) if lead.estimated_value is not None else None,
        "currency": lead.currency,
    }
    snapshot = ConversionSnapshot.objects.create(
        company=company,
        lead=lead,
        customer=customer,
        opportunity=opportunity,
        source_version=source_version,
        snapshot=snapshot_payload,
        converted_by_public_id=actor.user_public_id,
        converted_at=lead.converted_at,
    )
    _audit(
        actor=actor,
        company=company,
        action="crm.lead.converted",
        entity_type="crm_lead",
        entity_public_id=lead.public_id,
        before={"stage": old_stage_code, "version": source_version},
        after=snapshot_payload,
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.lead_converted",
        aggregate_type="crm_lead",
        aggregate_public_id=lead.public_id,
        aggregate_version=lead.version,
        payload={
            "customer_public_id": str(customer.public_id),
            "opportunity_public_id": str(opportunity.public_id),
        },
    )
    return snapshot


@transaction.atomic
def create_activity(
    *,
    company: Company,
    actor: RequestActor,
    activity_type: str,
    subject: str,
    notes: str = "",
    customer: Customer | None = None,
    contact: Contact | None = None,
    lead: Lead | None = None,
    opportunity: Opportunity | None = None,
    scheduled_for: datetime | None = None,
    follow_up_at: datetime | None = None,
    occurred_at: datetime | None = None,
    status: str = Activity.Status.PLANNED,
    direction: str = Activity.Direction.INTERNAL,
    outcome_code: str = "",
    duration_seconds: int | None = None,
    channel_metadata: dict[str, Any] | None = None,
    priority: str = Activity.Priority.NORMAL,
    owner_membership_public_id: uuid.UUID | None = None,
    location: dict[str, Any] | None = None,
) -> Activity:
    owner_id = owner_membership_public_id or actor.membership_public_id
    _assert_membership(company, owner_id)
    for record in (customer, contact, lead, opportunity):
        if record is not None and record.company_id != company.pk:
            raise ValidationError("Activity relation cannot cross companies")

    communication_types = {
        Activity.ActivityType.CALL,
        Activity.ActivityType.WHATSAPP,
        Activity.ActivityType.SMS,
        Activity.ActivityType.EMAIL,
    }
    if contact is None and activity_type in communication_types:
        if lead is not None and lead.primary_contact_id:
            contact = lead.primary_contact
        elif opportunity is not None and opportunity.primary_contact_id:
            contact = opportunity.primary_contact

    clean_metadata = dict(channel_metadata or {})
    # Protected endpoints never belong in activity metadata. Keep only channel/provider evidence.
    for protected_key in ("phone", "email", "recipient", "address"):
        clean_metadata.pop(protected_key, None)

    activity = Activity(
        company=company,
        customer=customer,
        contact=contact,
        lead=lead,
        opportunity=opportunity,
        activity_type=activity_type,
        status=status,
        direction=direction,
        outcome_code=outcome_code.strip().lower(),
        duration_seconds=duration_seconds,
        channel_metadata=clean_metadata,
        subject=subject.strip(),
        notes=notes.strip(),
        scheduled_for=scheduled_for,
        follow_up_at=follow_up_at,
        occurred_at=occurred_at,
        completed_at=timezone.now() if status == Activity.Status.COMPLETED else None,
        priority=priority,
        owner_membership_public_id=owner_id,
        created_by_public_id=actor.user_public_id,
        location=location or {},
    )
    activity.full_clean()
    activity.save()
    _audit(
        actor=actor,
        company=company,
        action="crm.activity.created",
        entity_type="crm_activity",
        entity_public_id=activity.public_id,
        after={
            "activity_type": activity.activity_type,
            "status": activity.status,
            "direction": activity.direction,
            "outcome_code": activity.outcome_code,
            "contact_public_id": str(contact.public_id) if contact else None,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.activity_created",
        aggregate_type="crm_activity",
        aggregate_public_id=activity.public_id,
        aggregate_version=activity.version,
        payload={
            "activity_type": activity.activity_type,
            "direction": activity.direction,
            "outcome_code": activity.outcome_code,
        },
    )
    if activity.status == Activity.Status.COMPLETED and not clean_metadata.get("automation_generated"):
        _dispatch_automation(company=company, actor=actor, trigger_code="activity.completed", record=activity)
    return activity


@transaction.atomic
def update_activity(
    *,
    company: Company,
    actor: RequestActor,
    activity_public_id: uuid.UUID,
    expected_version: int,
    status: str | None = None,
    direction: str | None = None,
    outcome_code: str | None = None,
    duration_seconds: int | None = None,
    notes: str | None = None,
    follow_up_at: datetime | None = None,
    occurred_at: datetime | None = None,
    scheduled_for: datetime | None = None,
    priority: str | None = None,
    channel_metadata: dict[str, Any] | None = None,
) -> Activity:
    activity = Activity.objects.select_for_update().filter(
        company=company,
        public_id=activity_public_id,
    ).first()
    if activity is None:
        raise ValidationError("CRM activity was not found")
    if activity.version != expected_version:
        raise ValidationError("CRM activity changed; refresh before updating the outcome")

    before = {
        "status": activity.status,
        "direction": activity.direction,
        "outcome_code": activity.outcome_code,
        "duration_seconds": activity.duration_seconds,
        "follow_up_at": activity.follow_up_at.isoformat() if activity.follow_up_at else None,
        "version": activity.version,
    }
    if status is not None:
        activity.status = status
        if status == Activity.Status.COMPLETED and activity.completed_at is None:
            activity.completed_at = timezone.now()
        elif status != Activity.Status.COMPLETED:
            activity.completed_at = None
    if direction is not None:
        activity.direction = direction
    if outcome_code is not None:
        activity.outcome_code = outcome_code.strip().lower()
    if duration_seconds is not None:
        activity.duration_seconds = duration_seconds
    if notes is not None:
        activity.notes = notes.strip()
    if follow_up_at is not None:
        activity.follow_up_at = follow_up_at
    if occurred_at is not None:
        activity.occurred_at = occurred_at
    if scheduled_for is not None:
        activity.scheduled_for = scheduled_for
    if priority is not None:
        activity.priority = priority
    if channel_metadata is not None:
        clean_metadata = dict(channel_metadata)
        for protected_key in ("phone", "email", "recipient", "address"):
            clean_metadata.pop(protected_key, None)
        activity.channel_metadata = clean_metadata

    activity.version += 1
    activity.full_clean()
    activity.save()
    _audit(
        actor=actor,
        company=company,
        action="crm.activity.updated",
        entity_type="crm_activity",
        entity_public_id=activity.public_id,
        before=before,
        after={
            "status": activity.status,
            "direction": activity.direction,
            "outcome_code": activity.outcome_code,
            "duration_seconds": activity.duration_seconds,
            "follow_up_at": activity.follow_up_at.isoformat() if activity.follow_up_at else None,
            "version": activity.version,
        },
    )
    _event(
        actor=actor,
        company=company,
        event_type="crm.activity_updated",
        aggregate_type="crm_activity",
        aggregate_public_id=activity.public_id,
        aggregate_version=activity.version,
        payload={
            "status": activity.status,
            "activity_type": activity.activity_type,
            "outcome_code": activity.outcome_code,
        },
    )
    if (
        before["status"] != Activity.Status.COMPLETED
        and activity.status == Activity.Status.COMPLETED
        and not (activity.channel_metadata or {}).get("automation_generated")
    ):
        _dispatch_automation(company=company, actor=actor, trigger_code="activity.completed", record=activity)
    return activity

