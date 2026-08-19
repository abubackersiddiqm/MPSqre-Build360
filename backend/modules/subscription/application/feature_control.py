from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from modules.subscription.application.entitlements import effective_entitlements
from modules.subscription.application.overrides import create_entitlement_override
from modules.subscription.models import EntitlementOverride
from modules.tenant.models import Company


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    code: str
    label: str
    group: str
    description: str
    legacy_codes: tuple[str, ...] = ()
    default_enabled: bool = False
    kind: str = "ADD_ON"
    requires: tuple[str, ...] = ()


# Tenant-sellable catalogue only. Platform release/cloud/control-plane operations are
# deliberately NOT subscription features: they remain ROOT_OPERATOR surfaces.
FEATURE_CATALOG: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("crm.core", "CRM", "Business modules", "Customers, protected contacts, leads, opportunities, activities and pipeline operations.", ("crm",), True, "MODULE"),
    FeatureDefinition("module.delivery", "Projects, Design & Estimation", "Business modules", "Project 360, project delivery, WBS, design review, estimation and BOQ workflows.", ("project", "projects", "design", "estimation"), True, "MODULE"),
    FeatureDefinition("module.supply", "Supply Chain", "Business modules", "Vendors, procurement, RFQs, purchase orders and inventory operations.", ("procurement", "vendor", "inventory"), True, "MODULE"),
    FeatureDefinition("module.field", "Field Operations", "Business modules", "Field execution, labour, site equipment, inspections and controlled site work.", ("field",), True, "MODULE"),
    FeatureDefinition("module.finance", "Finance & Commercial", "Business modules", "Budgets, invoices, payments, variations and commercial finance operations.", ("finance",), True, "MODULE"),
    FeatureDefinition("module.communication", "Communications", "Business modules", "Templates, consent, communication channels and delivery evidence.", ("communication",), True, "MODULE"),
    FeatureDefinition("module.reporting", "Reports & Operations", "Business modules", "Operational reporting, exports, data operations and management reporting.", ("reporting",), True, "MODULE"),
    FeatureDefinition("module.ai", "Governed AI", "Business modules", "Governed AI policies, grounded summaries, extraction review and risk signals.", ("ai",), True, "MODULE"),
    FeatureDefinition("module.integrations", "Integrations", "Business modules", "Provider-neutral integrations, connectors, webhooks and mapping profiles.", ("integration",), True, "MODULE"),
    FeatureDefinition("module.compliance", "Security & Compliance", "Business modules", "Tenant-facing controls, assessments, risks, exceptions and access reviews.", ("compliance",), True, "MODULE"),
    FeatureDefinition("module.people", "People Operations", "Business modules", "People, organization, employees, departments, leave and workforce administration.", ("people",), True, "MODULE"),
    FeatureDefinition("module.payroll", "Payroll", "Operations modules", "Payroll cycles, evidence and governed payroll operations.", (), True, "MODULE", ("module.people",)),
    FeatureDefinition("module.workforce", "Workforce Planning", "Operations modules", "Workforce planning, allocation and utilization controls.", (), True, "MODULE", ("module.people",)),
    FeatureDefinition("module.equipment", "Equipment Operations", "Operations modules", "Equipment operations, maintenance and utilization governance.", (), True, "MODULE"),
    FeatureDefinition("module.hse", "HSE & Safety", "Operations modules", "Health, safety, incident and compliance operations.", ("safety",), True, "MODULE"),
    FeatureDefinition("module.quality", "Quality & QA/QC", "Operations modules", "Quality assurance, inspections, NCR and QA/QC workflows.", ("quality",), True, "MODULE"),
    FeatureDefinition("module.documents", "Document Control", "Operations modules", "Controlled documents, transmittals, revisions and document evidence.", ("documents", "document_control"), True, "MODULE"),
    FeatureDefinition("module.commercial", "Contracts & Claims", "Operations modules", "Commercial operations, contracts, claims and governed commercial records.", ("commercial",), True, "MODULE"),
    FeatureDefinition("module.partner", "External Partner Portal", "Operations modules", "External collaboration, partner submissions and governed project access.", ("partner",), True, "MODULE"),
    FeatureDefinition("module.sustainability", "Sustainability & ESG", "Operations modules", "ESG, sustainability evidence and governed environmental operations.", ("sustainability",), True, "MODULE"),
    FeatureDefinition("module.digital_twin", "BIM & Digital Twin", "Operations modules", "Digital twin assets, BIM-linked evidence and handover asset visibility.", ("digital_twin",), True, "MODULE"),
    FeatureDefinition("module.facilities", "Facilities & Asset Lifecycle", "Operations modules", "Facilities, maintenance and post-handover asset lifecycle operations.", ("facilities",), True, "MODULE"),
    FeatureDefinition("module.property", "Property & Lease", "Operations modules", "Property, lease, tenant and occupancy operations.", ("property", "lease"), True, "MODULE"),
    FeatureDefinition("module.sales", "Development Sales", "Operations modules", "Development sales, bookings, collections and customer handover operations.", ("sales",), True, "MODULE"),
    FeatureDefinition("module.land", "Land & Approvals", "Operations modules", "Land acquisition, feasibility and statutory approval operations.", ("land",), True, "MODULE"),
    FeatureDefinition("module.capital", "Capital, JV & Investors", "Operations modules", "Capital planning, joint ventures, funding and investor operations.", ("capital",), True, "MODULE"),
    FeatureDefinition("module.risk_transfer", "Insurance & Risk Transfer", "Operations modules", "Insurance, bonds, guarantees and risk-transfer operations.", ("risk_transfer",), True, "MODULE"),
    FeatureDefinition("crm.meta_ads", "Meta Lead Ads", "CRM add-ons", "Governed Meta Lead Ads receipt, mapping and CRM lead ingestion.", ("crm",), False, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.ai_summary", "AI Relationship Summary", "CRM add-ons", "Grounded, cached relationship summary from governed CRM evidence with English and Tanglish views.", ("ai", "crm"), False, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.ai_recommendation", "AI Sales Copilot", "CRM add-ons", "Advisory next action, next-call preparation, attention signals and English/Tanglish follow-up drafts.", ("ai", "crm"), False, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.whatsapp", "CRM WhatsApp", "CRM add-ons", "Protected-number reveal for governed WhatsApp hand-off and activity evidence.", ("crm",), True, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.email", "CRM Email", "CRM add-ons", "CRM email interaction capability when a governed delivery workflow is available.", ("crm",), True, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.file_attachments", "CRM File Attachments", "CRM add-ons", "Governed Files attachments on CRM activities and the Lead Log Book.", ("files", "crm"), True, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.analytics", "CRM Analytics", "CRM add-ons", "CRM activity cockpit analytics and operational activity metrics.", ("reporting", "crm"), True, "ADD_ON", ("crm.core",)),
    FeatureDefinition("crm.automation", "CRM Automation", "CRM add-ons", "Industry-neutral rules that react to CRM events and create governed tasks, follow-ups, notes and assignments.", ("crm",), False, "ADD_ON", ("crm.core",)),
    FeatureDefinition("tenant.white_label", "White Label", "Tenant experience", "Tenant product name, logo, colors and branded experience.", ("white_label",), True, "ADD_ON"),
    FeatureDefinition("tenant.custom_domain", "Custom Domain", "Tenant experience", "Custom domain registration and governed activation foundation.", ("custom_domain",), True, "ADD_ON"),
    FeatureDefinition("platform.api_access", "External API Access", "Tenant experience", "Governed tenant API-client access for external integrations.", ("api",), False, "ADD_ON", ("module.integrations",)),
)

FEATURE_BY_CODE = {item.code: item for item in FEATURE_CATALOG}
MODULE_CODES = tuple(item.code for item in FEATURE_CATALOG if item.kind == "MODULE")

# Presets append explicit overrides so the result is stable even when catalogue defaults evolve.
PRESET_CATALOG: tuple[dict[str, object], ...] = (
    {
        "code": "CRM_ONLY",
        "label": "CRM only",
        "description": "Company users receive only CRM business capability; construction modules remain disabled.",
    },
    {
        "code": "CONSTRUCTION_CORE",
        "label": "Construction core",
        "description": "CRM + delivery + supply + field + finance + documents + commercial + reporting.",
    },
    {
        "code": "FULL_BUILD360",
        "label": "Full Build360",
        "description": "All sellable business and operations modules enabled. Add-ons remain governed individually where appropriate.",
    },
)


def _definition(code: str) -> FeatureDefinition:
    item = FEATURE_BY_CODE.get(code)
    if item is None:
        raise ValidationError(f"Unknown SaaS feature code: {code}")
    return item


def _configured_value(effective, definition: FeatureDefinition) -> tuple[bool, str]:
    if definition.code in effective.entitlements:
        return bool(effective.entitlements[definition.code]), "specific"
    for legacy_code in definition.legacy_codes:
        if legacy_code in effective.entitlements:
            return bool(effective.entitlements[legacy_code]), f"legacy:{legacy_code}"
    return definition.default_enabled, "compatibility-default"


def _effective_value(*, effective, definition: FeatureDefinition, stack: tuple[str, ...] = ()) -> tuple[bool, str]:
    configured, source = _configured_value(effective, definition)
    if not configured:
        return False, source
    if definition.code in stack:
        raise ValidationError(f"Circular SaaS feature dependency detected for {definition.code}")
    for required_code in definition.requires:
        required = _definition(required_code)
        required_enabled, _ = _effective_value(
            effective=effective,
            definition=required,
            stack=(*stack, definition.code),
        )
        if not required_enabled:
            return False, f"dependency:{required_code}"
    return True, source


def feature_enabled(*, company: Company, code: str, at: datetime | None = None) -> bool:
    definition = _definition(code)
    effective = effective_entitlements(company=company, at=at)
    value, _ = _effective_value(effective=effective, definition=definition)
    return value


def feature_matrix(*, company: Company, at: datetime | None = None) -> dict[str, object]:
    moment = at or timezone.now()
    effective = effective_entitlements(company=company, at=moment)
    active_overrides: dict[str, EntitlementOverride] = {}
    for item in (
        EntitlementOverride.objects.filter(
            company=company,
            entitlement_code__in=FEATURE_BY_CODE,
            effective_from__lte=moment,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=moment))
        .order_by("entitlement_code", "-effective_from")
    ):
        active_overrides.setdefault(item.entitlement_code, item)

    items: list[dict[str, object]] = []
    for definition in FEATURE_CATALOG:
        configured_enabled, configured_source = _configured_value(effective, definition)
        enabled, source = _effective_value(effective=effective, definition=definition)
        override = active_overrides.get(definition.code)
        if override is not None and source == configured_source:
            source = "override"
        items.append(
            {
                "code": definition.code,
                "label": definition.label,
                "group": definition.group,
                "kind": definition.kind,
                "description": definition.description,
                "enabled": enabled,
                "configured_enabled": configured_enabled,
                "source": source,
                "requires": list(definition.requires),
                "override": (
                    {
                        "public_id": str(override.public_id),
                        "enabled": override.enabled,
                        "reason_code": override.reason_code,
                        "effective_from": override.effective_from.isoformat(),
                        "set_by_public_id": str(override.set_by_public_id),
                    }
                    if override
                    else None
                ),
            }
        )
    return {
        "company": {
            "public_id": str(company.public_id),
            "code": company.code,
            "display_name": company.display_name,
        },
        "subscription": {
            "status": effective.subscription_status,
            "plan_code": effective.plan_code,
            "plan_version": effective.plan_version,
        },
        "presets": list(PRESET_CATALOG),
        "items": items,
        "generated_at": moment.isoformat(),
    }


def append_feature_override(
    *,
    company: Company,
    code: str,
    enabled: bool,
    reason_code: str,
    set_by_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> EntitlementOverride:
    _definition(code)
    reason = reason_code.strip()
    if not reason:
        raise ValidationError("Feature override reason is required")
    return create_entitlement_override(
        company=company,
        entitlement_code=code,
        enabled=enabled,
        limit_value=None,
        effective_from=timezone.now(),
        effective_to=None,
        reason_code=reason,
        actor_public_id=set_by_public_id,
        correlation_id=correlation_id,
    )


def _preset_values(preset_code: str) -> dict[str, bool]:
    code = preset_code.strip().upper()
    if code == "CRM_ONLY":
        values = {item.code: False for item in FEATURE_CATALOG}
        values.update(
            {
                "crm.core": True,
                "crm.whatsapp": True,
                "crm.email": True,
                "crm.file_attachments": True,
                "crm.analytics": True,
                "crm.automation": True,
            }
        )
        return values
    if code == "CONSTRUCTION_CORE":
        values = {item.code: False for item in FEATURE_CATALOG}
        for feature_code in (
            "crm.core",
            "module.delivery",
            "module.supply",
            "module.field",
            "module.finance",
            "module.reporting",
            "module.documents",
            "module.commercial",
            "crm.whatsapp",
            "crm.email",
            "crm.file_attachments",
            "crm.analytics",
            "crm.automation",
        ):
            values[feature_code] = True
        return values
    if code == "FULL_BUILD360":
        values = {item.code: True for item in FEATURE_CATALOG if item.kind == "MODULE"}
        values.update(
            {
                "crm.meta_ads": False,
                "crm.ai_summary": False,
                "crm.ai_recommendation": False,
                "crm.whatsapp": True,
                "crm.email": True,
                "crm.file_attachments": True,
                "crm.analytics": True,
                "crm.automation": True,
                "tenant.white_label": True,
                "tenant.custom_domain": True,
                "platform.api_access": False,
            }
        )
        return values
    raise ValidationError(f"Unknown SaaS package preset: {preset_code}")


def apply_feature_preset(
    *,
    company: Company,
    preset_code: str,
    reason_code: str,
    set_by_public_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> None:
    values = _preset_values(preset_code)
    reason = reason_code.strip()
    if not reason:
        raise ValidationError("Preset change reason is required")
    for code, enabled in values.items():
        append_feature_override(
            company=company,
            code=code,
            enabled=enabled,
            reason_code=f"{reason}:{preset_code.strip().upper()}",
            set_by_public_id=set_by_public_id,
            correlation_id=correlation_id,
        )
