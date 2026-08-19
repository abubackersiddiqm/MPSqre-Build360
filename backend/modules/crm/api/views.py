from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.ai.application.crm_lead_intelligence import (
    override as override_lead_intelligence,
)
from modules.ai.application.crm_lead_intelligence import (
    refresh as refresh_lead_intelligence,
)
from modules.ai.application.crm_lead_intelligence import (
    state as lead_intelligence_state,
)
from modules.crm.api.serializers import (
    ActivityAttachmentCreateSerializer,
    ActivityCreateSerializer,
    ActivityUpdateSerializer,
    ContactCreateSerializer,
    ContactRevealSerializer,
    ContactToLeadSerializer,
    CrmAutomationRuleCreateSerializer,
    CrmAutomationRuleUpdateSerializer,
    CrmCustomFieldCreateSerializer,
    CrmIndustryPackApplySerializer,
    CrmLeadSourceCreateSerializer,
    CrmPipelineCreateSerializer,
    CrmTerminologyUpdateSerializer,
    CustomerCreateSerializer,
    LeadAIOverrideSerializer,
    LeadConversionSerializer,
    LeadCreateSerializer,
    OpportunityCreateSerializer,
    OpportunityProjectConversionSerializer,
    PipelineStageCreateSerializer,
    StageTransitionSerializer,
)
from modules.crm.api.throttling import CrmContactRevealThrottle
from modules.crm.application.automation import (
    create_rule as create_automation_rule,
)
from modules.crm.application.automation import (
    execution_payload as automation_execution_payload,
)
from modules.crm.application.automation import (
    rule_payload as automation_rule_payload,
)
from modules.crm.application.automation import (
    update_rule as update_automation_rule,
)
from modules.crm.application.configuration import (
    apply_industry_pack,
    configuration_payload,
    create_custom_field,
    create_lead_source,
    create_pipeline,
    default_pipeline,
    ensure_foundation,
    update_terminology,
)
from modules.crm.application.logbook import (
    activity_attachment_download,
    activity_dashboard,
    attach_activity_file,
    attachment_payloads,
    creator_display_names,
    lead_card_queryset,
    lead_timeline,
    membership_display_names,
)
from modules.crm.application.protection import masked_email, masked_phone, normalize_name
from modules.crm.application.relationship import (
    account_page,
    account_workspace,
    my_work_payload,
    people_page,
    relationship_workspace,
)
from modules.crm.application.services import (
    RequestActor,
    contact_duplicates,
    convert_lead,
    create_activity,
    create_contact,
    create_customer,
    create_lead,
    create_opportunity,
    create_or_reuse_lead_from_contact,
    reveal_contact,
    transition_lead,
    transition_opportunity,
    update_activity,
)
from modules.crm.models import (
    Activity,
    ActivityAttachment,
    Contact,
    CrmAutomationExecution,
    CrmAutomationRule,
    CrmPipeline,
    Customer,
    Lead,
    Opportunity,
    PipelineStage,
)
from modules.platform.audit import request_metadata
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.api.base import TenantScopedAPIView


class CrmFeatureScopedAPIView(TenantScopedAPIView):
    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        if not feature_enabled(company=self.tenant_context.company, code="crm.core"):
            raise PermissionDenied("CRM Core is disabled for this company subscription")

    def require_saas_feature(self, code: str) -> None:
        if not feature_enabled(company=self.tenant_context.company, code=code):
            raise PermissionDenied("This CRM capability is disabled for this company subscription")


def _require_crm_setup_admin(view: TenantScopedAPIView) -> None:
    view.tenant_context.require("access.user.manage")
    view.tenant_context.require("crm.configuration.manage")


def _actor(view: TenantScopedAPIView, request: Request) -> RequestActor:
    request_id, ip_address, user_agent = request_metadata(request._request)
    return RequestActor(
        user_public_id=view.tenant_context.principal.user.public_id,
        membership_public_id=view.tenant_context.membership.public_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _limit(request: Request) -> int:
    try:
        return min(max(int(request.query_params.get("limit", "50")), 1), 100)
    except ValueError as exc:
        raise ValidationError("limit must be an integer") from exc


StageMap = dict[tuple[int | None, str], PipelineStage]


def _stage_map(rows) -> StageMap:
    return {(stage.pipeline_id, stage.code): stage for stage in rows}


def _available_stage_responses(stage: PipelineStage, stages: StageMap) -> list[dict[str, object]]:
    return [
        _stage_response(stages[(stage.pipeline_id, code)])
        for code in stage.allowed_next_codes
        if (stage.pipeline_id, code) in stages
    ]


def _stage_response(stage: PipelineStage) -> dict[str, object]:
    return {
        "public_id": str(stage.public_id),
        "entity_type": stage.entity_type,
        "pipeline_public_id": str(stage.pipeline.public_id) if stage.pipeline else None,
        "pipeline_code": stage.pipeline.code if stage.pipeline else "",
        "pipeline_name": stage.pipeline.name if stage.pipeline else "",
        "code": stage.code,
        "name": stage.name,
        "outcome": stage.outcome,
        "sort_order": stage.sort_order,
        "probability_percent": stage.probability_percent,
        "allowed_next_codes": stage.allowed_next_codes,
        "is_initial": stage.is_initial,
        "allows_conversion": stage.allows_conversion,
    }


def _contact_response(contact: Contact) -> dict[str, object]:
    return {
        "public_id": str(contact.public_id),
        "customer_public_id": str(contact.customer.public_id) if contact.customer else None,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "display_name": " ".join(part for part in [contact.first_name, contact.last_name] if part),
        "job_title": contact.job_title,
        "email_masked": masked_email(contact.email_last_four),
        "phone_masked": masked_phone(contact.phone_last_four),
        "alternate_phone_masked": masked_phone(contact.alternate_phone_last_four),
        "consent_status": contact.consent_status,
        "preferred_channel_code": contact.preferred_channel_code,
        "address": contact.address,
        "source_code": contact.source_code,
        "tags": contact.tags,
        "notes": contact.notes,
        "custom_fields": contact.custom_fields,
        "owner_membership_public_id": (
            str(contact.owner_membership_public_id)
            if contact.owner_membership_public_id
            else None
        ),
        "status": "active" if contact.is_active else "inactive",
        "is_primary": contact.is_primary,
        "is_active": contact.is_active,
        "version": contact.version,
        "communication_actions": {
            "email": bool(contact.email_ciphertext),
            "phone": bool(contact.phone_ciphertext),
            "alternate_phone": bool(contact.alternate_phone_ciphertext),
        },
    }


def _customer_response(customer: Customer) -> dict[str, object]:
    return {
        "public_id": str(customer.public_id),
        "kind": customer.kind,
        "display_name": customer.display_name,
        "legal_name": customer.legal_name,
        "external_reference": customer.external_reference,
        "source_code": customer.source_code,
        "custom_fields": customer.custom_fields,
        "status": customer.status,
        "owner_membership_public_id": (
            str(customer.owner_membership_public_id)
            if customer.owner_membership_public_id
            else None
        ),
        "version": customer.version,
        "created_at": customer.created_at.isoformat(),
    }


def _lead_response(lead: Lead, stages: StageMap) -> dict[str, object]:
    available = _available_stage_responses(lead.stage, stages)
    return {
        "public_id": str(lead.public_id),
        "title": lead.title,
        "description": lead.description,
        "source_code": lead.source_code,
        "pipeline_public_id": str(lead.stage.pipeline.public_id) if lead.stage.pipeline else None,
        "pipeline_name": lead.stage.pipeline.name if lead.stage.pipeline else "",
        "custom_fields": lead.custom_fields,
        "stage": _stage_response(lead.stage),
        "available_transitions": available,
        "customer": _customer_response(lead.customer) if lead.customer else None,
        "primary_contact": (
            _contact_response(lead.primary_contact) if lead.primary_contact else None
        ),
        "owner_membership_public_id": str(lead.owner_membership_public_id),
        "owner_display_name": getattr(lead, "owner_display_name_value", ""),
        "activity_count": int(getattr(lead, "activity_count_value", 0) or 0),
        "last_activity_at": (
            getattr(lead, "last_activity_at_value", None).isoformat()
            if getattr(lead, "last_activity_at_value", None)
            else None
        ),
        "next_activity_at": (
            getattr(lead, "next_activity_at_value", None).isoformat()
            if getattr(lead, "next_activity_at_value", None)
            else None
        ),
        "estimated_value": str(lead.estimated_value) if lead.estimated_value is not None else None,
        "currency": lead.currency,
        "next_follow_up_at": lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None,
        "version": lead.version,
        "created_at": lead.created_at.isoformat(),
        "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
    }


def _opportunity_response(
    opportunity: Opportunity,
    stages: StageMap,
) -> dict[str, object]:
    available = _available_stage_responses(opportunity.stage, stages)
    return {
        "public_id": str(opportunity.public_id),
        "name": opportunity.name,
        "customer": _customer_response(opportunity.customer),
        "primary_contact": (
            _contact_response(opportunity.primary_contact)
            if opportunity.primary_contact
            else None
        ),
        "source_lead_public_id": (
            str(opportunity.source_lead.public_id) if opportunity.source_lead else None
        ),
        "pipeline_public_id": str(opportunity.stage.pipeline.public_id) if opportunity.stage.pipeline else None,
        "pipeline_name": opportunity.stage.pipeline.name if opportunity.stage.pipeline else "",
        "custom_fields": opportunity.custom_fields,
        "stage": _stage_response(opportunity.stage),
        "available_transitions": available,
        "owner_membership_public_id": str(opportunity.owner_membership_public_id),
        "amount": str(opportunity.amount),
        "currency": opportunity.currency,
        "expected_close_date": (
            opportunity.expected_close_date.isoformat()
            if opportunity.expected_close_date
            else None
        ),
        "probability_percent": opportunity.probability_percent,
        "version": opportunity.version,
        "created_at": opportunity.created_at.isoformat(),
    }


def _activity_response(
    activity: Activity,
    *,
    attachment_map: dict[int, dict[str, object]] | None = None,
    creator_names: dict[uuid.UUID, str] | None = None,
) -> dict[str, object]:
    attachments = list(activity.attachments.all()) if hasattr(activity, "attachments") else []
    return {
        "public_id": str(activity.public_id),
        "activity_type": activity.activity_type,
        "status": activity.status,
        "direction": activity.direction,
        "outcome_code": activity.outcome_code,
        "duration_seconds": activity.duration_seconds,
        "channel_metadata": activity.channel_metadata,
        "priority": activity.priority,
        "subject": activity.subject,
        "notes": activity.notes,
        "customer_public_id": str(activity.customer.public_id) if activity.customer else None,
        "contact_public_id": str(activity.contact.public_id) if activity.contact else None,
        "lead_public_id": str(activity.lead.public_id) if activity.lead else None,
        "opportunity_public_id": (
            str(activity.opportunity.public_id) if activity.opportunity else None
        ),
        "scheduled_for": activity.scheduled_for.isoformat() if activity.scheduled_for else None,
        "follow_up_at": activity.follow_up_at.isoformat() if activity.follow_up_at else None,
        "occurred_at": activity.occurred_at.isoformat() if activity.occurred_at else None,
        "completed_at": activity.completed_at.isoformat() if activity.completed_at else None,
        "created_at": activity.created_at.isoformat(),
        "created_by_public_id": str(activity.created_by_public_id),
        "created_by_name": (creator_names or {}).get(activity.created_by_public_id, ""),
        "location": activity.location,
        "attachments": [
            (attachment_map or {}).get(row.pk, {"public_id": str(row.public_id)})
            for row in attachments
        ],
        "version": activity.version,
    }


def _validation_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(exc.messages)


class CrmAutomationRuleListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.require_saas_feature("crm.automation")
        self.tenant_context.require("crm.automation.read")
        rows = CrmAutomationRule.objects.filter(company=self.tenant_context.company).order_by("priority", "name")
        return Response({
            "items": [automation_rule_payload(row) for row in rows],
            "triggers": [
                {"code": code, "label": label}
                for code, label in CrmAutomationRule.TriggerCode.choices
            ],
            "action_types": [
                {"code": "create_task", "label": "Create task"},
                {"code": "schedule_follow_up", "label": "Schedule follow-up"},
                {"code": "add_note", "label": "Add internal note"},
                {"code": "assign_owner", "label": "Assign owner"},
                {"code": "set_lead_follow_up", "label": "Set lead next follow-up"},
            ],
        })

    def post(self, request: Request) -> Response:
        self.require_saas_feature("crm.automation")
        self.tenant_context.require("crm.automation.manage")
        serializer = CrmAutomationRuleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rule = create_automation_rule(company=self.tenant_context.company, **serializer.validated_data)
        except (DjangoValidationError, IntegrityError) as exc:
            if isinstance(exc, DjangoValidationError):
                raise _validation_error(exc) from exc
            raise ValidationError("Automation code already exists for this company") from exc
        return Response(automation_rule_payload(rule), status=201)


class CrmAutomationRuleDetailView(CrmFeatureScopedAPIView):
    def patch(self, request: Request, public_id: uuid.UUID) -> Response:
        self.require_saas_feature("crm.automation")
        self.tenant_context.require("crm.automation.manage")
        serializer = CrmAutomationRuleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        expected_version = int(changes.pop("expected_version"))
        try:
            rule = update_automation_rule(
                company=self.tenant_context.company,
                public_id=public_id,
                expected_version=expected_version,
                changes=changes,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(automation_rule_payload(rule))


class CrmAutomationExecutionListView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.require_saas_feature("crm.automation")
        self.tenant_context.require("crm.automation.read")
        rows = CrmAutomationExecution.objects.select_related("rule").filter(company=self.tenant_context.company)
        rule_public_id = request.query_params.get("rule_public_id")
        if rule_public_id:
            rows = rows.filter(rule__public_id=rule_public_id)
        rows = rows.order_by("-started_at")[: _limit(request)]
        return Response({"items": [automation_execution_payload(row) for row in rows]})


class CrmConfigurationView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.configuration.read")
        return Response(configuration_payload(self.tenant_context.company))

    def patch(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = CrmTerminologyUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            update_terminology(
                company=self.tenant_context.company,
                terminology=serializer.validated_data["terminology"],
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(configuration_payload(self.tenant_context.company))


class CrmIndustryPackApplyView(CrmFeatureScopedAPIView):
    def post(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = CrmIndustryPackApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            apply_industry_pack(
                company=self.tenant_context.company,
                pack_code=serializer.validated_data["pack_code"],
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(configuration_payload(self.tenant_context.company))


class CrmPipelineListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.configuration.read")
        ensure_foundation(self.tenant_context.company)
        entity_type = request.query_params.get("entity_type")
        rows = CrmPipeline.objects.filter(company=self.tenant_context.company, is_active=True)
        if entity_type:
            rows = rows.filter(entity_type=entity_type)
        return Response({"items": [row for row in configuration_payload(self.tenant_context.company)["pipelines"] if not entity_type or row["entity_type"] == entity_type]})

    def post(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = CrmPipelineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pipeline = create_pipeline(company=self.tenant_context.company, **serializer.validated_data)
        except (DjangoValidationError, IntegrityError) as exc:
            if isinstance(exc, DjangoValidationError):
                raise _validation_error(exc) from exc
            raise ValidationError("Pipeline code already exists or default pipeline conflicts") from exc
        return Response({
            "public_id": str(pipeline.public_id), "entity_type": pipeline.entity_type, "code": pipeline.code,
            "name": pipeline.name, "description": pipeline.description, "is_default": pipeline.is_default,
            "sort_order": pipeline.sort_order, "stage_count": 0,
        }, status=201)


class CrmCustomFieldListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.configuration.read")
        payload = configuration_payload(self.tenant_context.company)["custom_fields"]
        entity_type = request.query_params.get("entity_type")
        return Response({"items": [row for row in payload if not entity_type or row["entity_type"] == entity_type]})

    def post(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = CrmCustomFieldCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            field = create_custom_field(company=self.tenant_context.company, **serializer.validated_data)
        except (DjangoValidationError, IntegrityError) as exc:
            if isinstance(exc, DjangoValidationError):
                raise _validation_error(exc) from exc
            raise ValidationError("Custom field code already exists for this CRM record type") from exc
        return Response({
            "public_id": str(field.public_id), "entity_type": field.entity_type, "code": field.code,
            "label": field.label, "field_type": field.field_type, "help_text": field.help_text,
            "is_required": field.is_required, "options": field.options, "sort_order": field.sort_order,
            "source_pack_code": field.source_pack_code,
        }, status=201)


class CrmLeadSourceListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.configuration.read")
        return Response({"items": configuration_payload(self.tenant_context.company)["lead_sources"]})

    def post(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = CrmLeadSourceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            source = create_lead_source(company=self.tenant_context.company, **serializer.validated_data)
        except (DjangoValidationError, IntegrityError) as exc:
            if isinstance(exc, DjangoValidationError):
                raise _validation_error(exc) from exc
            raise ValidationError("Lead source code already exists") from exc
        return Response({
            "public_id": str(source.public_id), "code": source.code, "name": source.name,
            "channel_type": source.channel_type, "sort_order": source.sort_order, "source_pack_code": source.source_pack_code,
        }, status=201)


class CrmSummaryView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.dashboard.read")
        company = self.tenant_context.company
        weighted = ExpressionWrapper(
            F("amount") * F("probability_percent") / Decimal("100"),
            output_field=DecimalField(max_digits=19, decimal_places=4),
        )
        pipeline = Opportunity.objects.filter(company=company).aggregate(
            total=Sum("amount"),
            weighted=Sum(weighted),
        )
        lead_stage_counts = list(
            Lead.objects.filter(company=company)
            .values("stage__code", "stage__name")
            .annotate(count=Count("id"))
            .order_by("stage__sort_order")
        )
        opportunity_stage_counts = list(
            Opportunity.objects.filter(company=company)
            .values("stage__code", "stage__name")
            .annotate(count=Count("id"), amount=Sum("amount"))
            .order_by("stage__sort_order")
        )
        overdue_followups = Lead.objects.filter(
            company=company,
            next_follow_up_at__lt=timezone.now(),
            converted_at__isnull=True,
            disqualified_at__isnull=True,
        ).count()
        return Response(
            {
                "customers": Customer.objects.filter(company=company, status="active").count(),
                "contacts": Contact.objects.filter(company=company, is_active=True).count(),
                "leads": Lead.objects.filter(company=company).count(),
                "opportunities": Opportunity.objects.filter(company=company).count(),
                "overdue_followups": overdue_followups,
                "pipeline_total": str(pipeline["total"] or Decimal("0")),
                "weighted_pipeline": str(pipeline["weighted"] or Decimal("0")),
                "currency": company.currency,
                "lead_stages": lead_stage_counts,
                "opportunity_stages": opportunity_stage_counts,
            }
        )


class PipelineStageListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.stage.read")
        entity_type = request.query_params.get("entity_type")
        ensure_foundation(self.tenant_context.company)
        queryset = PipelineStage.objects.select_related("pipeline").filter(company=self.tenant_context.company, is_active=True)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        pipeline_public_id = request.query_params.get("pipeline")
        if pipeline_public_id:
            queryset = queryset.filter(pipeline__public_id=pipeline_public_id)
        return Response({"items": [_stage_response(stage) for stage in queryset]})

    def post(self, request: Request) -> Response:
        _require_crm_setup_admin(self)
        serializer = PipelineStageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        pipeline_public_id = data.pop("pipeline_public_id", None)
        try:
            with transaction.atomic():
                if pipeline_public_id:
                    pipeline = CrmPipeline.objects.filter(
                        company=self.tenant_context.company,
                        public_id=pipeline_public_id,
                        entity_type=data["entity_type"],
                        is_active=True,
                    ).first()
                    if pipeline is None:
                        raise ValidationError("CRM pipeline was not found")
                else:
                    pipeline = default_pipeline(self.tenant_context.company, data["entity_type"])
                if data.get("is_initial"):
                    PipelineStage.objects.filter(
                        company=self.tenant_context.company,
                        pipeline=pipeline,
                        entity_type=data["entity_type"],
                        is_initial=True,
                    ).update(is_initial=False)
                stage = PipelineStage(
                    company=self.tenant_context.company,
                    pipeline=pipeline,
                    **data,
                )
                stage.full_clean()
                stage.save()
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        except IntegrityError as exc:
            raise ValidationError("Stage code already exists in this CRM pipeline") from exc
        return Response(_stage_response(stage), status=201)


class CustomerListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.customer.read")
        queryset = Customer.objects.filter(company=self.tenant_context.company)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(normalized_name__icontains=search.lower())
        items = queryset.order_by("-created_at")[: _limit(request)]
        return Response({"items": [_customer_response(customer) for customer in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("crm.customer.manage")
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            customer = create_customer(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(_customer_response(customer), status=201)


class CustomerDetailView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.customer.read")
        customer = Customer.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if customer is None:
            raise NotFound("Resource not found")
        contacts = Contact.objects.filter(company=self.tenant_context.company, customer=customer)
        return Response(
            {
                **_customer_response(customer),
                "contacts": [_contact_response(contact) for contact in contacts],
            }
        )


class ContactListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.contact.read")
        queryset = Contact.objects.select_related("customer").filter(
            company=self.tenant_context.company,
            is_active=True,
        )
        customer_id = request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer__public_id=customer_id)
        return Response(
            {"items": [_contact_response(contact) for contact in queryset[: _limit(request)]]}
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("crm.contact.manage")
        serializer = ContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        customer_id = data.pop("customer_public_id", None)
        customer = None
        if customer_id:
            customer = Customer.objects.filter(
                company=self.tenant_context.company,
                public_id=customer_id,
            ).first()
            if customer is None:
                raise NotFound("Resource not found")
        try:
            contact = create_contact(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                customer=customer,
                **data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(_contact_response(contact), status=201)


class ContactDuplicateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.contact.read")
        contacts = contact_duplicates(
            company=self.tenant_context.company,
            email=request.query_params.get("email", ""),
            phone=request.query_params.get("phone", ""),
            alternate_phone=request.query_params.get("alternate_phone", ""),
        )[:20]
        return Response({"items": [_contact_response(contact) for contact in contacts]})


class ContactRevealView(CrmFeatureScopedAPIView):
    throttle_classes = [CrmContactRevealThrottle]

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.contact.reveal")
        serializer = ContactRevealSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason_code = serializer.validated_data["reason_code"]
        if reason_code == "crm_whatsapp":
            self.require_saas_feature("crm.whatsapp")
        elif reason_code == "crm_email":
            self.require_saas_feature("crm.email")
        if not Contact.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).exists():
            raise NotFound("Resource not found")
        try:
            values = reveal_contact(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                contact_public_id=public_id,
                reason_code=serializer.validated_data["reason_code"],
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        response = Response(values)
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Pragma"] = "no-cache"
        return response


class ContactToLeadView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.contact.read")
        self.tenant_context.require("crm.lead.manage")
        serializer = ContactToLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lead, created = create_or_reuse_lead_from_contact(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                contact_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        stages = _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.LEAD,
                is_active=True,
            )
        )
        owner_names = membership_display_names(
            company=self.tenant_context.company,
            public_ids={lead.owner_membership_public_id},
        )
        lead.activity_count_value = lead.activities.count()
        lead.last_activity_at_value = lead.activities.order_by("-created_at").values_list("created_at", flat=True).first()
        lead.next_activity_at_value = lead.activities.filter(
            status=Activity.Status.PLANNED,
            scheduled_for__gte=timezone.now(),
        ).order_by("scheduled_for").values_list("scheduled_for", flat=True).first()
        lead.owner_display_name_value = owner_names.get(lead.owner_membership_public_id, "")
        return Response({**_lead_response(lead, stages), "created": created}, status=201 if created else 200)


class LeadListCreateView(CrmFeatureScopedAPIView):
    def _stages(self) -> StageMap:
        return _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.LEAD,
                is_active=True,
            )
        )

    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.lead.read")
        queryset = lead_card_queryset(company=self.tenant_context.company)
        stage_code = request.query_params.get("stage")
        if stage_code:
            queryset = queryset.filter(stage__code=stage_code)
        pipeline_public_id = request.query_params.get("pipeline")
        if pipeline_public_id:
            queryset = queryset.filter(stage__pipeline__public_id=pipeline_public_id)
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(title__icontains=search)
        items = list(queryset.order_by("-created_at")[: _limit(request)])
        owner_names = membership_display_names(
            company=self.tenant_context.company,
            public_ids={item.owner_membership_public_id for item in items},
        )
        for item in items:
            item.owner_display_name_value = owner_names.get(item.owner_membership_public_id, "")
        stages = self._stages()
        return Response({"items": [_lead_response(lead, stages) for lead in items]})

    def post(self, request: Request) -> Response:
        self.tenant_context.require("crm.lead.manage")
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        customer_id = data.pop("customer_public_id", None)
        primary_contact_id = data.pop("primary_contact_public_id", None)
        customer_display_name = data.pop("customer_display_name", "")
        contact_first_name = data.pop("contact_first_name", "")
        contact_last_name = data.pop("contact_last_name", "")
        contact_email = data.pop("contact_email", "")
        contact_phone = data.pop("contact_phone", "")
        contact_alternate_phone = data.pop("contact_alternate_phone", "")
        actor = _actor(self, request)
        owner_id = data.get("owner_membership_public_id")
        if (
            owner_id
            and owner_id != self.tenant_context.membership.public_id
            and not self.tenant_context.can("crm.lead.assign")
        ):
            raise ValidationError("Lead assignment permission is required")
        try:
            with transaction.atomic():
                customer = None
                if customer_id:
                    customer = Customer.objects.filter(
                        company=self.tenant_context.company,
                        public_id=customer_id,
                    ).first()
                    if customer is None:
                        raise NotFound("Resource not found")
                elif customer_display_name:
                    customer = Customer.objects.filter(
                        company=self.tenant_context.company,
                        normalized_name=normalize_name(customer_display_name),
                        status=Customer.Status.ACTIVE,
                    ).first()
                    if customer is None:
                        customer = create_customer(
                            company=self.tenant_context.company,
                            actor=actor,
                            kind=Customer.Kind.ORGANIZATION,
                            display_name=customer_display_name,
                            source_code=str(data.get("source_code", "")),
                        )
                contact = None
                if primary_contact_id:
                    contact = Contact.objects.select_related("customer").filter(
                        company=self.tenant_context.company,
                        public_id=primary_contact_id,
                        is_active=True,
                    ).first()
                    if contact is None:
                        raise NotFound("Resource not found")
                    if customer is None and contact.customer_id:
                        customer = contact.customer
                elif contact_first_name and (contact_email or contact_phone):
                    duplicate = contact_duplicates(
                        company=self.tenant_context.company,
                        email=contact_email,
                        phone=contact_phone,
                        alternate_phone=contact_alternate_phone,
                    ).first()
                    if duplicate is not None:
                        contact = duplicate
                        if customer is None and contact.customer_id:
                            customer = contact.customer
                    else:
                        contact = create_contact(
                            company=self.tenant_context.company,
                            actor=actor,
                            customer=customer,
                            first_name=contact_first_name,
                            last_name=contact_last_name,
                            email=contact_email,
                            phone=contact_phone,
                            alternate_phone=contact_alternate_phone,
                            is_primary=True,
                        )
                lead = create_lead(
                    company=self.tenant_context.company,
                    actor=actor,
                    customer=customer,
                    primary_contact=contact,
                    **data,
                )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        stages = self._stages()
        return Response(_lead_response(lead, stages), status=201)


class LeadDetailView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.read")
        lead = lead_card_queryset(company=self.tenant_context.company).filter(
            public_id=public_id,
        ).first()
        if lead is None:
            raise NotFound("Resource not found")
        stages = _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.LEAD,
                is_active=True,
            )
        )
        owner_names = membership_display_names(
            company=self.tenant_context.company,
            public_ids={lead.owner_membership_public_id},
        )
        lead.owner_display_name_value = owner_names.get(lead.owner_membership_public_id, "")
        activities = list(
            Activity.objects.prefetch_related("attachments").filter(
                company=self.tenant_context.company,
                lead=lead,
            ).order_by("-created_at")[:50]
        )
        attachments = [item for activity in activities for item in activity.attachments.all()]
        attachment_map = attachment_payloads(company=self.tenant_context.company, attachments=attachments)
        creator_names = creator_display_names({item.created_by_public_id for item in activities})
        return Response(
            {
                **_lead_response(lead, stages),
                "activities": [
                    _activity_response(
                        activity,
                        attachment_map=attachment_map,
                        creator_names=creator_names,
                    )
                    for activity in activities
                ],
            }
        )


class LeadTransitionView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.transition")
        serializer = StageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lead = transition_lead(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                lead_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        stages = _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.LEAD,
                is_active=True,
            )
        )
        return Response(_lead_response(lead, stages))


class LeadConvertView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.convert")
        serializer = LeadConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            snapshot = convert_lead(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                lead_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(
            {
                "public_id": str(snapshot.public_id),
                "lead_public_id": str(snapshot.lead.public_id),
                "customer_public_id": str(snapshot.customer.public_id),
                "opportunity_public_id": str(snapshot.opportunity.public_id),
                "source_version": snapshot.source_version,
                "converted_at": snapshot.converted_at.isoformat(),
                "snapshot": snapshot.snapshot,
            }
        )


class OpportunityListCreateView(CrmFeatureScopedAPIView):
    def _stages(self) -> StageMap:
        return _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.OPPORTUNITY,
                is_active=True,
            )
        )

    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.opportunity.read")
        queryset = Opportunity.objects.select_related(
            "stage", "stage__pipeline", "customer", "primary_contact", "source_lead"
        ).filter(company=self.tenant_context.company)
        stage_code = request.query_params.get("stage")
        if stage_code:
            queryset = queryset.filter(stage__code=stage_code)
        pipeline_public_id = request.query_params.get("pipeline")
        if pipeline_public_id:
            queryset = queryset.filter(stage__pipeline__public_id=pipeline_public_id)
        items = queryset.order_by("stage__sort_order", "-amount")[: _limit(request)]
        stages = self._stages()
        return Response(
            {"items": [_opportunity_response(opportunity, stages) for opportunity in items]}
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("crm.opportunity.manage")
        serializer = OpportunityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        customer_id = data.pop("customer_public_id")
        contact_id = data.pop("primary_contact_public_id", None)
        customer = Customer.objects.filter(
            company=self.tenant_context.company,
            public_id=customer_id,
        ).first()
        if customer is None:
            raise NotFound("Resource not found")
        contact = None
        if contact_id:
            contact = Contact.objects.filter(
                company=self.tenant_context.company,
                public_id=contact_id,
            ).first()
            if contact is None:
                raise NotFound("Resource not found")
        owner_id = data.get("owner_membership_public_id")
        if (
            owner_id
            and owner_id != self.tenant_context.membership.public_id
            and not self.tenant_context.can("crm.opportunity.assign")
        ):
            raise ValidationError("Opportunity assignment permission is required")
        try:
            opportunity = create_opportunity(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                customer=customer,
                primary_contact=contact,
                **data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(_opportunity_response(opportunity, self._stages()), status=201)


class OpportunityTransitionView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.opportunity.transition")
        serializer = StageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            opportunity = transition_opportunity(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                opportunity_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        stages = _stage_map(
            PipelineStage.objects.select_related("pipeline").filter(
                company=self.tenant_context.company,
                entity_type=PipelineStage.EntityType.OPPORTUNITY,
                is_active=True,
            )
        )
        return Response(_opportunity_response(opportunity, stages))


def _existing_project_response(project, message: str) -> Response:
    return Response({
        "public_id": str(project.public_id),
        "code": project.code,
        "name": project.name,
        "created": False,
        "message": message,
    })


def _create_opportunity_project(view: TenantScopedAPIView, request: Request, opportunity: Opportunity, data: dict[str, Any], *, preconstruction: bool) -> Response:
    from modules.projects.application.services import create_project
    from modules.projects.models import Project

    existing = Project.objects.select_related("stage").filter(
        company=view.tenant_context.company,
        opportunity_public_id=opportunity.public_id,
    ).first()
    if existing is not None:
        return _existing_project_response(
            existing,
            "Existing preconstruction/project workspace returned for this opportunity.",
        )

    code = str(data.get("code") or f"PRJ-{str(opportunity.public_id).replace('-', '')[-8:]}").upper()
    name = str(data.get("name") or opportunity.name)
    purpose = "Preconstruction workspace" if preconstruction else "Controlled project"
    try:
        project = create_project(
            company=view.tenant_context.company,
            actor=_actor(view, request),
            code=code,
            name=name,
            description=str(data.get("description") or f"{purpose} created from CRM opportunity {opportunity.name}"),
            customer_public_id=opportunity.customer.public_id,
            opportunity_public_id=opportunity.public_id,
            location=data.get("location") or {},
            planned_start_date=data.get("planned_start_date"),
            planned_end_date=data.get("planned_end_date"),
            currency=opportunity.currency,
            approved_budget=opportunity.amount,
        )
    except DjangoValidationError as exc:
        raise _validation_error(exc) from exc
    except IntegrityError:
        existing = Project.objects.filter(
            company=view.tenant_context.company,
            opportunity_public_id=opportunity.public_id,
        ).first()
        if existing is None:
            raise
        return _existing_project_response(
            existing,
            "Concurrent request resolved to the existing controlled project.",
        )
    return Response({
        "public_id": str(project.public_id),
        "code": project.code,
        "name": project.name,
        "created": True,
        "preconstruction": preconstruction,
        "message": (
            "Preconstruction workspace created. Continue with architect/design and estimation before final award."
            if preconstruction
            else "Won opportunity converted into the controlled project exactly once."
        ),
    }, status=201)


class OpportunityPreconstructionView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.require_saas_feature("module.delivery")
        self.tenant_context.require("crm.opportunity.manage")
        self.tenant_context.require("project.project.manage")
        serializer = OpportunityProjectConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        opportunity = Opportunity.objects.select_related("customer", "stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if opportunity is None:
            raise NotFound("Resource not found")
        if opportunity.stage.outcome == PipelineStage.Outcome.LOST:
            raise ValidationError("A lost opportunity cannot start preconstruction without being reopened")
        return _create_opportunity_project(
            self, request, opportunity, dict(serializer.validated_data), preconstruction=True
        )


class OpportunityProjectConvertView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.require_saas_feature("module.delivery")
        self.tenant_context.require("crm.opportunity.manage")
        self.tenant_context.require("project.project.manage")
        serializer = OpportunityProjectConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        opportunity = Opportunity.objects.select_related("customer", "stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if opportunity is None:
            raise NotFound("Resource not found")
        if opportunity.stage.outcome != PipelineStage.Outcome.WON:
            raise ValidationError("Only a won opportunity can be converted into a project")

        return _create_opportunity_project(
            self, request, opportunity, dict(serializer.validated_data), preconstruction=False
        )


class ActivityListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.activity.read")
        queryset = Activity.objects.select_related(
            "customer", "contact", "lead", "opportunity"
        ).prefetch_related("attachments").filter(
            company=self.tenant_context.company
        )
        status_code = request.query_params.get("status", "").strip()
        if status_code:
            queryset = queryset.filter(status=status_code)
        activity_type = request.query_params.get("activity_type", "").strip()
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        priority = request.query_params.get("priority", "").strip()
        if priority:
            queryset = queryset.filter(priority=priority)
        owner = request.query_params.get("owner", "").strip()
        if owner:
            queryset = queryset.filter(owner_membership_public_id=owner)
        lead_id = request.query_params.get("lead", "").strip()
        if lead_id:
            queryset = queryset.filter(lead__public_id=lead_id)
        contact_id = request.query_params.get("contact", "").strip()
        if contact_id:
            queryset = queryset.filter(contact__public_id=contact_id)
        source = request.query_params.get("source", "").strip()
        if source:
            queryset = queryset.filter(lead__source_code__iexact=source)
        date_from = request.query_params.get("date_from", "").strip()
        if date_from:
            queryset = queryset.filter(scheduled_for__date__gte=date_from)
        date_to = request.query_params.get("date_to", "").strip()
        if date_to:
            queryset = queryset.filter(scheduled_for__date__lte=date_to)
        now = timezone.now()
        if request.query_params.get("overdue") == "1":
            queryset = queryset.filter(
                status=Activity.Status.PLANNED,
                scheduled_for__lt=now,
            )
        activities = list(
            queryset.order_by("-scheduled_for", "-created_at")[: _limit(request)]
        )
        attachments = [
            attachment
            for activity in activities
            for attachment in activity.attachments.all()
        ]
        attachment_map = attachment_payloads(company=self.tenant_context.company, attachments=attachments)
        creator_names = creator_display_names(
            {activity.created_by_public_id for activity in activities}
        )
        return Response(
            {
                "items": [
                    _activity_response(
                        activity,
                        attachment_map=attachment_map,
                        creator_names=creator_names,
                    )
                    for activity in activities
                ]
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("crm.activity.manage")
        serializer = ActivityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity_type = serializer.validated_data["activity_type"]
        if activity_type == Activity.ActivityType.WHATSAPP:
            self.require_saas_feature("crm.whatsapp")
        elif activity_type == Activity.ActivityType.EMAIL:
            self.require_saas_feature("crm.email")
        data: dict[str, Any] = dict(serializer.validated_data)
        relations: dict[str, Any] = {}
        relation_map = {
            "customer_public_id": ("customer", Customer),
            "contact_public_id": ("contact", Contact),
            "lead_public_id": ("lead", Lead),
            "opportunity_public_id": ("opportunity", Opportunity),
        }
        for key, (target, model) in relation_map.items():
            public_id = data.pop(key, None)
            if public_id:
                record = model.objects.filter(
                    company=self.tenant_context.company,
                    public_id=public_id,
                ).first()
                if record is None:
                    raise NotFound("Resource not found")
                relations[target] = record
        try:
            activity = create_activity(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                **relations,
                **data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(_activity_response(activity), status=201)


class ActivityDetailView(CrmFeatureScopedAPIView):
    def patch(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.activity.manage")
        serializer = ActivityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            activity = update_activity(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                activity_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(_activity_response(activity))


class ContactTimelineView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.contact_center.use")
        self.tenant_context.require("crm.contact.read")
        self.tenant_context.require("crm.activity.read")
        contact = Contact.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
            is_active=True,
        ).first()
        if contact is None:
            raise NotFound("Resource not found")
        try:
            limit = min(max(int(request.query_params.get("limit", "100")), 1), 300)
        except ValueError as exc:
            raise ValidationError("limit must be an integer") from exc
        activities = list(
            Activity.objects.select_related("customer", "contact", "lead", "opportunity")
            .prefetch_related("attachments")
            .filter(company=self.tenant_context.company, contact=contact)
            .order_by("-occurred_at", "-created_at")[:limit]
        )
        attachments = [
            attachment
            for activity in activities
            for attachment in activity.attachments.all()
        ]
        attachment_map = attachment_payloads(
            company=self.tenant_context.company,
            attachments=attachments,
        )
        creator_names = creator_display_names(
            {activity.created_by_public_id for activity in activities}
        )
        return Response({
            "contact": _contact_response(contact),
            "items": [
                _activity_response(
                    activity,
                    attachment_map=attachment_map,
                    creator_names=creator_names,
                )
                for activity in activities
            ],
        })


class LeadTimelineView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.read")
        lead = Lead.objects.select_related("stage").filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if lead is None:
            raise NotFound("Resource not found")
        try:
            limit = min(max(int(request.query_params.get("limit", "200")), 1), 500)
        except ValueError as exc:
            raise ValidationError("limit must be an integer") from exc
        return Response(
            lead_timeline(
                company=self.tenant_context.company,
                lead=lead,
                limit=limit,
            )
        )


class ActivityDashboardView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.activity.read")
        self.require_saas_feature("crm.analytics")
        return Response(activity_dashboard(company=self.tenant_context.company))


class CrmMyWorkView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.dashboard.read")
        try:
            limit = min(max(int(request.query_params.get("limit", "40")), 10), 100)
        except ValueError as exc:
            raise ValidationError("limit must be an integer") from exc
        return Response(
            my_work_payload(
                company=self.tenant_context.company,
                membership_public_id=self.tenant_context.membership.public_id,
                limit=limit,
                include_contacts=self.tenant_context.can("crm.contact.read"),
                include_customers=self.tenant_context.can("crm.customer.read"),
                include_leads=self.tenant_context.can("crm.lead.read"),
                include_activities=self.tenant_context.can("crm.activity.read"),
            )
        )


class CrmPeopleView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.contact.read")
        try:
            page = max(int(request.query_params.get("page", "1")), 1)
            page_size = min(max(int(request.query_params.get("page_size", "50")), 10), 100)
        except ValueError as exc:
            raise ValidationError("page and page_size must be integers") from exc
        return Response(
            people_page(
                company=self.tenant_context.company,
                membership_public_id=self.tenant_context.membership.public_id,
                search=request.query_params.get("search", ""),
                view=request.query_params.get("view", "all"),
                stage=request.query_params.get("stage", ""),
                source=request.query_params.get("source", ""),
                owner=request.query_params.get("owner", ""),
                customer_public_id=request.query_params.get("customer", ""),
                sort=request.query_params.get("sort", "next_action"),
                page=page,
                page_size=page_size,
                include_leads=self.tenant_context.can("crm.lead.read"),
                include_opportunities=self.tenant_context.can("crm.opportunity.read"),
                include_activities=self.tenant_context.can("crm.activity.read"),
                include_customers=self.tenant_context.can("crm.customer.read"),
            )
        )


class CrmRelationshipWorkspaceView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.contact.read")
        try:
            limit = min(max(int(request.query_params.get("limit", "250")), 50), 500)
        except ValueError as exc:
            raise ValidationError("limit must be an integer") from exc
        try:
            payload = relationship_workspace(
                company=self.tenant_context.company,
                contact_public_id=public_id,
                limit=limit,
                include_leads=self.tenant_context.can("crm.lead.read"),
                include_opportunities=self.tenant_context.can("crm.opportunity.read"),
                include_activities=self.tenant_context.can("crm.activity.read"),
                include_customers=self.tenant_context.can("crm.customer.read"),
            )
        except Contact.DoesNotExist as exc:
            raise NotFound("Resource not found") from exc
        return Response(payload)


class CrmAccountView(CrmFeatureScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("crm.customer.read")
        try:
            page = max(int(request.query_params.get("page", "1")), 1)
            page_size = min(max(int(request.query_params.get("page_size", "50")), 10), 100)
        except ValueError as exc:
            raise ValidationError("page and page_size must be integers") from exc
        return Response(
            account_page(
                company=self.tenant_context.company,
                search=request.query_params.get("search", ""),
                page=page,
                page_size=page_size,
                include_contacts=self.tenant_context.can("crm.contact.read"),
                include_leads=self.tenant_context.can("crm.lead.read"),
                include_opportunities=self.tenant_context.can("crm.opportunity.read"),
                include_activities=self.tenant_context.can("crm.activity.read"),
            )
        )


class CrmAccountWorkspaceView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.customer.read")
        try:
            payload = account_workspace(
                company=self.tenant_context.company,
                customer_public_id=public_id,
                include_contacts=self.tenant_context.can("crm.contact.read"),
                include_leads=self.tenant_context.can("crm.lead.read"),
                include_opportunities=self.tenant_context.can("crm.opportunity.read"),
                include_activities=self.tenant_context.can("crm.activity.read"),
            )
        except Customer.DoesNotExist as exc:
            raise NotFound("Resource not found") from exc
        return Response(payload)


class ActivityAttachmentListCreateView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.activity.read")
        self.require_saas_feature("crm.file_attachments")
        activity = Activity.objects.filter(
            company=self.tenant_context.company,
            public_id=public_id,
        ).first()
        if activity is None:
            raise NotFound("Resource not found")
        attachments = list(
            ActivityAttachment.objects.select_related("activity").filter(
                company=self.tenant_context.company,
                activity=activity,
            ).order_by("created_at")
        )
        payloads = attachment_payloads(company=self.tenant_context.company, attachments=attachments)
        return Response({"items": [payloads[item.pk] for item in attachments]})

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.activity.manage")
        self.tenant_context.require("files.upload")
        self.require_saas_feature("crm.file_attachments")
        serializer = ActivityAttachmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            attachment = attach_activity_file(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                activity_public_id=public_id,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        payload = attachment_payloads(company=self.tenant_context.company, attachments=[attachment])[attachment.pk]
        return Response(payload, status=201)


class ActivityAttachmentDownloadView(CrmFeatureScopedAPIView):
    def get(
        self,
        request: Request,
        public_id: uuid.UUID,
        attachment_public_id: uuid.UUID,
    ) -> Response:
        self.tenant_context.require("crm.activity.read")
        self.require_saas_feature("crm.file_attachments")
        try:
            payload = activity_attachment_download(
                company=self.tenant_context.company,
                actor=_actor(self, request),
                activity_public_id=public_id,
                attachment_public_id=attachment_public_id,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        return Response(payload)



class LeadIntelligenceView(CrmFeatureScopedAPIView):
    def get(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.read")
        self.tenant_context.require("crm.activity.read")
        self.tenant_context.require("ai.crm_lead.read")
        try:
            return Response(
                lead_intelligence_state(
                    company=self.tenant_context.company,
                    lead_public_id=public_id,
                )
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc

    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.read")
        self.tenant_context.require("crm.activity.read")
        self.tenant_context.require("ai.crm_lead.generate")
        try:
            return Response(
                refresh_lead_intelligence(
                    company=self.tenant_context.company,
                    actor=_actor(self, request),
                    lead_public_id=public_id,
                )
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc


class LeadIntelligenceOverrideView(CrmFeatureScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("crm.lead.read")
        self.tenant_context.require("ai.crm_lead.override")
        serializer = LeadAIOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        due_at = values.get("suggested_due_at")
        values["suggested_due_at"] = due_at.isoformat() if due_at else None
        try:
            return Response(
                override_lead_intelligence(
                    company=self.tenant_context.company,
                    actor=_actor(self, request),
                    lead_public_id=public_id,
                    **values,
                )
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
