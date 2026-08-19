from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.crm.models import (
    CrmCustomFieldDefinition,
    CrmLeadSource,
    CrmPipeline,
    CrmTenantProfile,
    PipelineStage,
)
from modules.tenant.models import Company

DEFAULT_TERMINOLOGY = {
    "customer": "Customer",
    "contact": "Contact",
    "lead": "Lead",
    "opportunity": "Opportunity",
    "pipeline": "Pipeline",
    "quote": "Quote",
}

COMMON_SOURCES = [
    ("manual", "Manual entry", "manual"),
    ("website", "Website", "website"),
    ("phone", "Phone call", "phone"),
    ("whatsapp", "WhatsApp", "whatsapp"),
    ("email", "Email", "email"),
    ("referral", "Referral", "referral"),
    ("partner", "Partner", "partner"),
    ("event", "Event / expo", "event"),
    ("meta_ads", "Meta Ads", "ads"),
    ("google_ads", "Google Ads", "ads"),
    ("import", "Import", "import"),
    ("api", "API / integration", "api"),
]

GENERAL_LEAD_STAGES = [
    ("new", "New", "open", 10, 5, ["contacted", "qualified", "disqualified"], True, False),
    ("contacted", "Contacted", "open", 20, 15, ["qualified", "disqualified"], False, False),
    ("qualified", "Qualified", "qualified", 30, 30, ["converted", "disqualified"], False, True),
    ("converted", "Converted", "converted", 90, 100, [], False, False),
    ("disqualified", "Disqualified", "disqualified", 100, 0, [], False, False),
]

GENERAL_OPPORTUNITY_STAGES = [
    ("qualification", "Qualification", "open", 10, 20, ["proposal", "lost"], True, False),
    ("proposal", "Proposal", "open", 20, 45, ["negotiation", "lost"], False, False),
    ("negotiation", "Negotiation", "open", 30, 70, ["won", "lost"], False, False),
    ("won", "Won", "won", 90, 100, [], False, False),
    ("lost", "Lost", "lost", 100, 0, [], False, False),
]

PACKS: dict[str, dict[str, Any]] = {
    "general": {
        "name": "General Business",
        "description": "Neutral CRM for sales and service businesses.",
        "terminology": {},
        "custom_fields": [],
    },
    "construction": {
        "name": "Construction",
        "description": "Construction enquiry fields without coupling CRM Core to project execution.",
        "terminology": {"opportunity": "Opportunity", "quote": "Estimate / Proposal"},
        "custom_fields": [
            ("lead", "project_type", "Project type", "select", ["Residential", "Commercial", "Industrial", "Infrastructure"]),
            ("lead", "site_location", "Site location", "text", []),
            ("lead", "built_up_area", "Built-up area", "number", []),
            ("lead", "budget", "Budget", "currency", []),
            ("lead", "construction_stage", "Construction stage", "select", ["Planning", "Design", "Approval", "Ready to start", "Ongoing"]),
        ],
    },
    "real_estate": {
        "name": "Real Estate",
        "description": "Property sales and booking CRM starter pack.",
        "terminology": {"customer": "Buyer", "opportunity": "Booking Opportunity"},
        "custom_fields": [
            ("lead", "property_type", "Property type", "select", ["Apartment", "Villa", "Plot", "Commercial"]),
            ("lead", "preferred_location", "Preferred location", "text", []),
            ("lead", "bedrooms", "Bedrooms", "number", []),
            ("lead", "budget", "Budget", "currency", []),
        ],
    },
    "interior": {
        "name": "Interior Design",
        "description": "Interior enquiry and design-sales starter pack.",
        "terminology": {"quote": "Design Proposal"},
        "custom_fields": [
            ("lead", "property_type", "Property type", "select", ["Apartment", "Villa", "Office", "Retail", "Other"]),
            ("lead", "area", "Area", "number", []),
            ("lead", "possession_date", "Possession date", "date", []),
            ("lead", "budget", "Budget", "currency", []),
        ],
    },
    "automobile": {
        "name": "Automobile",
        "description": "Vehicle sales, dealership and automotive service starter pack.",
        "terminology": {"customer": "Customer", "opportunity": "Deal"},
        "custom_fields": [
            ("lead", "vehicle_brand", "Vehicle brand", "text", []),
            ("lead", "vehicle_model", "Vehicle model", "text", []),
            ("lead", "purchase_timeline", "Purchase timeline", "select", ["Immediate", "30 days", "60 days", "90+ days"]),
            ("lead", "finance_required", "Finance required", "boolean", []),
        ],
    },
    "financial_services": {
        "name": "Financial Services",
        "description": "Loan, insurance and financial-product enquiry starter pack.",
        "terminology": {"lead": "Applicant", "opportunity": "Application"},
        "custom_fields": [
            ("lead", "product_type", "Product type", "text", []),
            ("lead", "requested_amount", "Requested amount", "currency", []),
            ("lead", "employment_type", "Employment type", "select", ["Salaried", "Self employed", "Business", "Other"]),
            ("lead", "preferred_provider", "Preferred provider", "text", []),
        ],
    },
    "manufacturing": {
        "name": "Manufacturing / Trading",
        "description": "B2B enquiry and quotation starter pack.",
        "terminology": {"customer": "Account", "opportunity": "Deal"},
        "custom_fields": [
            ("lead", "product_category", "Product category", "text", []),
            ("lead", "quantity", "Quantity", "number", []),
            ("lead", "required_by", "Required by", "date", []),
            ("lead", "specification", "Specification", "long_text", []),
        ],
    },
    "professional_services": {
        "name": "Professional Services",
        "description": "Consulting, agency, legal, accounting and service-business starter pack.",
        "terminology": {"opportunity": "Engagement"},
        "custom_fields": [
            ("lead", "service_required", "Service required", "text", []),
            ("lead", "target_start_date", "Target start date", "date", []),
            ("lead", "budget", "Budget", "currency", []),
        ],
    },
    "other": {
        "name": "Other / Custom",
        "description": "Start neutral and configure fields, labels and sources for your business.",
        "terminology": {},
        "custom_fields": [],
    },
}


def industry_pack_catalogue() -> list[dict[str, str]]:
    return [
        {"code": code, "name": value["name"], "description": value["description"]}
        for code, value in PACKS.items()
    ]


def ensure_profile(company: Company) -> CrmTenantProfile:
    profile, _ = CrmTenantProfile.objects.get_or_create(
        company=company,
        defaults={"industry_code": "general", "terminology": DEFAULT_TERMINOLOGY.copy()},
    )
    merged = {**DEFAULT_TERMINOLOGY, **(profile.terminology or {})}
    if merged != profile.terminology:
        profile.terminology = merged
        profile.save(update_fields=["terminology", "updated_at"])
    return profile


def default_pipeline(company: Company, entity_type: str) -> CrmPipeline:
    pipeline = CrmPipeline.objects.filter(
        company=company,
        entity_type=entity_type,
        is_default=True,
        is_active=True,
    ).first()
    if pipeline is not None:
        return pipeline
    pipeline = CrmPipeline.objects.filter(
        company=company,
        entity_type=entity_type,
        is_active=True,
    ).order_by("sort_order", "created_at").first()
    if pipeline is not None:
        pipeline.is_default = True
        pipeline.save(update_fields=["is_default", "updated_at"])
        return pipeline
    return CrmPipeline.objects.create(
        company=company,
        entity_type=entity_type,
        code=f"default-{entity_type}",
        name="Lead Pipeline" if entity_type == "lead" else "Sales Pipeline",
        sort_order=10,
        is_default=True,
        source_pack_code="general",
    )


def ensure_foundation(company: Company) -> CrmTenantProfile:
    profile = ensure_profile(company)
    now = timezone.now()
    for entity_type, definitions in (
        ("lead", GENERAL_LEAD_STAGES),
        ("opportunity", GENERAL_OPPORTUNITY_STAGES),
    ):
        pipeline = default_pipeline(company, entity_type)
        existing = PipelineStage.objects.filter(company=company, entity_type=entity_type)
        existing.filter(pipeline__isnull=True).update(pipeline=pipeline)
        if not existing.exists():
            for code, name, outcome, order, probability, next_codes, initial, converts in definitions:
                PipelineStage.objects.create(
                    company=company,
                    pipeline=pipeline,
                    entity_type=entity_type,
                    code=code,
                    name=name,
                    outcome=outcome,
                    sort_order=order,
                    probability_percent=probability,
                    allowed_next_codes=next_codes,
                    is_initial=initial,
                    allows_conversion=converts,
                    is_active=True,
                    effective_from=now,
                )
    if not CrmLeadSource.objects.filter(company=company).exists():
        for index, (code, name, channel) in enumerate(COMMON_SOURCES, start=1):
            CrmLeadSource.objects.create(
                company=company,
                code=code,
                name=name,
                channel_type=channel,
                sort_order=index * 10,
                source_pack_code="general",
            )
    return profile


@transaction.atomic
def apply_industry_pack(*, company: Company, pack_code: str) -> CrmTenantProfile:
    if pack_code not in PACKS:
        raise ValidationError("Unknown CRM industry pack")
    profile = ensure_foundation(company)
    pack = PACKS[pack_code]
    profile.industry_code = pack_code
    profile.terminology = {**DEFAULT_TERMINOLOGY, **pack.get("terminology", {})}
    profile.version += 1
    profile.save(update_fields=["industry_code", "terminology", "version", "updated_at"])
    # Keep user-created fields, but hide starter fields from a previously selected
    # industry pack. Values already stored on CRM records are intentionally kept.
    CrmCustomFieldDefinition.objects.filter(
        company=company,
        is_active=True,
    ).exclude(source_pack_code__in=["", "general", pack_code]).update(is_active=False)
    for entity_type, code, label, field_type, options in pack.get("custom_fields", []):
        CrmCustomFieldDefinition.objects.update_or_create(
            company=company,
            entity_type=entity_type,
            code=code,
            defaults={
                "label": label,
                "field_type": field_type,
                "options": options,
                "source_pack_code": pack_code,
                "is_active": True,
            },
        )
    return profile


@transaction.atomic
def update_terminology(*, company: Company, terminology: dict[str, Any]) -> CrmTenantProfile:
    profile = ensure_foundation(company)
    allowed = set(DEFAULT_TERMINOLOGY)
    cleaned: dict[str, str] = {}
    for key, value in terminology.items():
        if key not in allowed:
            continue
        text = str(value or "").strip()
        if not text:
            raise ValidationError({key: "Label cannot be blank"})
        cleaned[key] = text[:80]
    profile.terminology = {**DEFAULT_TERMINOLOGY, **profile.terminology, **cleaned}
    profile.version += 1
    profile.save(update_fields=["terminology", "version", "updated_at"])
    return profile


@transaction.atomic
def create_pipeline(
    *,
    company: Company,
    entity_type: str,
    code: str,
    name: str,
    description: str = "",
    is_default: bool = False,
) -> CrmPipeline:
    if entity_type not in {"lead", "opportunity"}:
        raise ValidationError("Unsupported CRM pipeline entity")
    if is_default:
        CrmPipeline.objects.filter(
            company=company,
            entity_type=entity_type,
            is_default=True,
            is_active=True,
        ).update(is_default=False)
    return CrmPipeline.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        name=name.strip(),
        description=description.strip(),
        is_default=is_default,
    )


def _validate_slug(value: str) -> str:
    code = value.strip().lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code):
        raise ValidationError("Code must start with a letter and contain only lowercase letters, numbers and underscores")
    return code


@transaction.atomic
def create_custom_field(
    *,
    company: Company,
    entity_type: str,
    code: str,
    label: str,
    field_type: str,
    help_text: str = "",
    is_required: bool = False,
    options: list[Any] | None = None,
    sort_order: int = 100,
) -> CrmCustomFieldDefinition:
    code = _validate_slug(code)
    if field_type in {"select", "multiselect"} and not options:
        raise ValidationError({"options": "Dropdown fields require at least one option"})
    return CrmCustomFieldDefinition.objects.create(
        company=company,
        entity_type=entity_type,
        code=code,
        label=label.strip(),
        field_type=field_type,
        help_text=help_text.strip(),
        is_required=is_required,
        options=options or [],
        sort_order=sort_order,
    )


@transaction.atomic
def create_lead_source(
    *, company: Company, code: str, name: str, channel_type: str, sort_order: int = 100
) -> CrmLeadSource:
    return CrmLeadSource.objects.create(
        company=company,
        code=_validate_slug(code),
        name=name.strip(),
        channel_type=channel_type,
        sort_order=sort_order,
    )


def validate_custom_fields(*, company: Company, entity_type: str, values: dict[str, Any] | None) -> dict[str, Any]:
    values = values or {}
    definitions = list(
        CrmCustomFieldDefinition.objects.filter(
            company=company, entity_type=entity_type, is_active=True
        ).order_by("sort_order", "label")
    )
    errors: dict[str, list[str]] = {}
    known = {definition.code: definition for definition in definitions}
    unknown = sorted(set(values) - set(known))
    if unknown:
        errors["custom_fields"] = [f"Unknown custom field(s): {', '.join(unknown)}"]
    for definition in definitions:
        value = values.get(definition.code)
        empty = value is None or value == "" or value == []
        if definition.is_required and empty:
            errors.setdefault(definition.code, []).append("This custom field is required")
            continue
        if empty:
            continue
        if definition.field_type in {"number", "currency", "percent"}:
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors.setdefault(definition.code, []).append("Enter a numeric value")
                continue
            if definition.field_type == "percent" and not 0 <= number <= 100:
                errors.setdefault(definition.code, []).append("Percentage must be between 0 and 100")
        elif definition.field_type == "boolean" and not isinstance(value, bool):
            errors.setdefault(definition.code, []).append("Enter true or false")
        elif definition.field_type == "select" and definition.options and value not in definition.options:
            errors.setdefault(definition.code, []).append("Select a configured option")
        elif definition.field_type == "multiselect":
            if not isinstance(value, list):
                errors.setdefault(definition.code, []).append("Enter a list of configured options")
            elif definition.options and any(item not in definition.options for item in value):
                errors.setdefault(definition.code, []).append("One or more selections are not configured")
    if errors:
        raise ValidationError(errors)
    return values


def configuration_payload(company: Company) -> dict[str, Any]:
    profile = ensure_foundation(company)
    pipelines = list(CrmPipeline.objects.filter(company=company, is_active=True).order_by("entity_type", "sort_order"))
    fields = list(CrmCustomFieldDefinition.objects.filter(company=company, is_active=True).order_by("entity_type", "sort_order", "label"))
    sources = list(CrmLeadSource.objects.filter(company=company, is_active=True).order_by("sort_order", "name"))
    stages = list(
        PipelineStage.objects.select_related("pipeline")
        .filter(company=company, is_active=True)
        .order_by("entity_type", "pipeline__sort_order", "sort_order", "name")
    )
    return {
        "profile": {
            "public_id": str(profile.public_id),
            "industry_code": profile.industry_code,
            "terminology": {**DEFAULT_TERMINOLOGY, **(profile.terminology or {})},
            "settings": profile.settings,
            "version": profile.version,
        },
        "industry_packs": industry_pack_catalogue(),
        "pipelines": [
            {
                "public_id": str(row.public_id),
                "entity_type": row.entity_type,
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "is_default": row.is_default,
                "sort_order": row.sort_order,
                "stage_count": row.stages.filter(is_active=True).count(),
            }
            for row in pipelines
        ],
        "stages": [
            {
                "public_id": str(row.public_id),
                "pipeline_public_id": str(row.pipeline.public_id) if row.pipeline else None,
                "entity_type": row.entity_type,
                "code": row.code,
                "name": row.name,
                "outcome": row.outcome,
                "sort_order": row.sort_order,
                "probability_percent": row.probability_percent,
                "allowed_next_codes": row.allowed_next_codes,
                "is_initial": row.is_initial,
                "allows_conversion": row.allows_conversion,
            }
            for row in stages
        ],
        "custom_fields": [
            {
                "public_id": str(row.public_id),
                "entity_type": row.entity_type,
                "code": row.code,
                "label": row.label,
                "field_type": row.field_type,
                "help_text": row.help_text,
                "is_required": row.is_required,
                "options": row.options,
                "sort_order": row.sort_order,
                "source_pack_code": row.source_pack_code,
            }
            for row in fields
        ],
        "lead_sources": [
            {
                "public_id": str(row.public_id),
                "code": row.code,
                "name": row.name,
                "channel_type": row.channel_type,
                "sort_order": row.sort_order,
                "source_pack_code": row.source_pack_code,
            }
            for row in sources
        ],
    }
