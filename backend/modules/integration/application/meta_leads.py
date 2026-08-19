from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.crm.application.services import (
    RequestActor as CrmRequestActor,
)
from modules.crm.application.services import (
    contact_duplicates,
    create_activity,
    create_contact,
)
from modules.crm.models import Activity, Contact
from modules.integration.application.services import (
    create_connector,
    create_mapping_profile,
    publish_mapping_profile,
    transition_connector_status,
)
from modules.integration.models import (
    ConnectorProfile,
    DataMappingProfile,
    MetaLeadReceipt,
)
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import Company, Membership

META_PROVIDER_CODE = "META_LEAD_ADS"
META_SOURCE_CODE = "META_ADS"
META_SOURCE_FACEBOOK = "FACEBOOK"
META_SOURCE_INSTAGRAM = "INSTAGRAM"
META_ACTIVITY_PROVIDER = "meta_lead_ads"
DEFAULT_MAPPING_CODE = "META_LEAD_DEFAULT"
DEFAULT_MAPPINGS = [
    {"source": "first_name", "target": "contact.first_name"},
    {"source": "last_name", "target": "contact.last_name"},
    {"source": "full_name", "target": "contact.full_name"},
    {"source": "email", "target": "contact.email"},
    {"source": "phone_number", "target": "contact.phone"},
    {"source": "phone", "target": "contact.phone"},
    {"source": "company_name", "target": "lead.company_name"},
    {"source": "job_title", "target": "contact.job_title"},
    {"source": "city", "target": "contact.address.city"},
    {"source": "state", "target": "contact.address.state"},
]


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _audit(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_type: str,
    entity_public_id: uuid.UUID,
    after: dict[str, Any],
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
            after=after,
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


def require_meta_ads_entitlement(company: Company) -> None:
    if not feature_enabled(company=company, code="crm.meta_ads"):
        raise PermissionDenied("Meta Lead Ads is not included in the active subscription")


def _active_owner(company: Company, membership_public_id: uuid.UUID) -> Membership:
    now = timezone.now()
    membership = (
        Membership.objects.select_related("user")
        .filter(
            company=company,
            public_id=membership_public_id,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
            effective_from__lte=now,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if membership is None or not membership.user.is_active:
        raise ValidationError("Default Meta lead owner must be an active company membership")
    return membership


def _validate_secret_reference(secret_ref: str) -> str:
    reference = secret_ref.strip()
    if not reference.startswith("env://"):
        raise ValidationError(
            "Meta Lead Ads currently requires an env:// secret reference; raw tokens are never stored in ConnectorProfile."
        )
    name = reference.removeprefix("env://").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{1,127}", name):
        raise ValidationError("Meta secret reference must point to a valid environment variable")
    return reference


def _secret_bundle(connector: ConnectorProfile) -> dict[str, str]:
    reference = _validate_secret_reference(connector.secret_ref)
    variable = reference.removeprefix("env://")
    raw = os.getenv(variable, "").strip()
    if not raw:
        raise ValidationError(f"Configured Meta secret environment variable {variable} is not available")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "Meta secret environment variable must contain JSON with page_access_token and app_secret"
        ) from exc
    if not isinstance(data, dict):
        raise ValidationError("Meta secret bundle must be a JSON object")
    page_access_token = str(data.get("page_access_token") or "").strip()
    app_secret = str(data.get("app_secret") or "").strip()
    if not page_access_token or not app_secret:
        raise ValidationError("Meta secret bundle requires page_access_token and app_secret")
    return {"page_access_token": page_access_token, "app_secret": app_secret}


def _graph_version(connector: ConnectorProfile) -> str:
    value = str(connector.public_config.get("graph_api_version") or "").strip()
    if not re.fullmatch(r"v\d{1,2}\.\d{1,2}", value):
        raise ValidationError("Configure a valid Meta Graph API version such as vXX.X")
    return value


def _config_owner(connector: ConnectorProfile) -> Membership:
    raw = connector.public_config.get("default_owner_membership_public_id")
    try:
        public_id = uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Configure a default CRM owner membership for Meta leads") from exc
    return _active_owner(connector.company, public_id)


def _connector_contract(connector: ConnectorProfile, *, resolve_secret: bool) -> None:
    if connector.provider_code != META_PROVIDER_CODE:
        raise ValidationError("Connector is not a Meta Lead Ads connector")
    require_meta_ads_entitlement(connector.company)
    page_id = str(connector.public_config.get("page_id") or "").strip()
    if not page_id:
        raise ValidationError("Meta Page ID is required")
    forms = connector.public_config.get("lead_form_ids") or []
    if not isinstance(forms, list):
        raise ValidationError("lead_form_ids must be a list")
    _graph_version(connector)
    _config_owner(connector)
    _validate_secret_reference(connector.secret_ref)
    digest = str(connector.public_config.get("webhook_verify_token_digest") or "")
    if len(digest) != 64:
        raise ValidationError("Webhook verification token has not been initialized")
    if resolve_secret:
        _secret_bundle(connector)


def connector_payload(connector: ConnectorProfile) -> dict[str, Any]:
    config = connector.public_config or {}
    return {
        "public_id": str(connector.public_id),
        "code": connector.code,
        "name": connector.name,
        "status": connector.status,
        "health_status": connector.health_status,
        "page_id": str(config.get("page_id") or ""),
        "page_name": str(config.get("page_name") or ""),
        "lead_form_ids": list(config.get("lead_form_ids") or []),
        "graph_api_version": str(config.get("graph_api_version") or ""),
        "default_owner_membership_public_id": str(config.get("default_owner_membership_public_id") or ""),
        "mapping_code": str(config.get("mapping_code") or DEFAULT_MAPPING_CODE),
        "verify_token_last_four": str(config.get("webhook_verify_token_last_four") or ""),
        "has_secret_reference": bool(connector.secret_ref),
        "webhook_path": f"/api/v1/integrations/meta-leads/webhook/{connector.public_id}",
        "version": connector.version,
    }


@transaction.atomic
def create_meta_connector(
    *,
    company: Company,
    actor: RequestActor,
    code: str,
    name: str,
    page_id: str,
    page_name: str,
    lead_form_ids: list[str],
    graph_api_version: str,
    default_owner_membership_public_id: uuid.UUID,
    secret_ref: str,
) -> tuple[ConnectorProfile, str]:
    require_meta_ads_entitlement(company)
    _active_owner(company, default_owner_membership_public_id)
    _validate_secret_reference(secret_ref)
    if not re.fullmatch(r"v\d{1,2}\.\d{1,2}", graph_api_version.strip()):
        raise ValidationError("Graph API version must use the vXX.X format")
    forms = sorted({str(value).strip() for value in lead_form_ids if str(value).strip()})
    verify_token = secrets.token_urlsafe(32)
    public_config = {
        "page_id": page_id.strip(),
        "page_name": page_name.strip(),
        "lead_form_ids": forms,
        "graph_api_version": graph_api_version.strip(),
        "default_owner_membership_public_id": str(default_owner_membership_public_id),
        "mapping_code": DEFAULT_MAPPING_CODE,
        "webhook_verify_token_digest": hashlib.sha256(verify_token.encode("utf-8")).hexdigest(),
        "webhook_verify_token_last_four": verify_token[-4:],
    }
    connector = create_connector(
        company=company,
        actor=actor,
        code=code,
        name=name,
        connector_type=ConnectorProfile.ConnectorType.CUSTOM,
        provider_code=META_PROVIDER_CODE,
        direction=ConnectorProfile.Direction.INBOUND,
        base_url="https://graph.facebook.com",
        public_config=public_config,
        secret_ref=secret_ref,
        allowed_data_classes=["crm_contact", "crm_lead", "integration_metadata"],
    )
    mapping = create_mapping_profile(
        company=company,
        actor=actor,
        connector_public_id=connector.public_id,
        code=DEFAULT_MAPPING_CODE,
        name="Meta Lead Ads default CRM field mapping",
        source_schema_code="META_LEAD_ADS_FIELD_DATA",
        target_schema_code="CRM_CONTACT_LEAD",
        mappings=DEFAULT_MAPPINGS,
        transformations=[],
    )
    publish_mapping_profile(
        company=company,
        actor=actor,
        public_id=mapping.public_id,
    )
    _audit(
        actor=actor,
        company=company,
        action="integration.meta_leads.configured",
        entity_type="connector_profile",
        entity_public_id=connector.public_id,
        after={"page_id": page_id.strip(), "form_count": len(forms), "raw_secret_stored": False},
    )
    return connector, verify_token


@transaction.atomic
def rotate_verify_token(
    *,
    company: Company,
    actor: RequestActor,
    connector_public_id: uuid.UUID,
    expected_version: int,
) -> tuple[ConnectorProfile, str]:
    connector = (
        ConnectorProfile.objects.select_for_update()
        .filter(company=company, public_id=connector_public_id, provider_code=META_PROVIDER_CODE)
        .first()
    )
    if connector is None:
        raise ValidationError("Meta connector was not found")
    require_meta_ads_entitlement(company)
    if connector.version != expected_version:
        raise ValidationError("Connector changed; refresh before retrying")
    raw = secrets.token_urlsafe(32)
    config = dict(connector.public_config or {})
    config["webhook_verify_token_digest"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    config["webhook_verify_token_last_four"] = raw[-4:]
    connector.public_config = config
    connector.version += 1
    connector.save(update_fields=["public_config", "version", "updated_at"])
    _audit(
        actor=actor,
        company=company,
        action="integration.meta_leads.verify_token_rotated",
        entity_type="connector_profile",
        entity_public_id=connector.public_id,
        after={"verify_token_last_four": raw[-4:]},
    )
    return connector, raw


def verify_webhook_challenge(
    *,
    connector: ConnectorProfile,
    mode: str,
    verify_token: str,
    challenge: str,
) -> str:
    if connector.status != ConnectorProfile.Status.ACTIVE:
        raise ValidationError("Meta connector is not active")
    require_meta_ads_entitlement(connector.company)
    if mode != "subscribe":
        raise ValidationError("Invalid webhook verification mode")
    expected = str(connector.public_config.get("webhook_verify_token_digest") or "")
    actual = hashlib.sha256(verify_token.encode("utf-8")).hexdigest()
    if not expected or not hmac.compare_digest(expected, actual):
        raise ValidationError("Webhook verification failed")
    return challenge


def verify_webhook_signature(*, connector: ConnectorProfile, raw_body: bytes, signature: str) -> None:
    if connector.status != ConnectorProfile.Status.ACTIVE:
        raise ValidationError("Meta connector is not active")
    bundle = _secret_bundle(connector)
    presented = signature.strip()
    if not presented.startswith("sha256="):
        raise ValidationError("Webhook signature is missing or invalid")
    expected = "sha256=" + hmac.new(
        bundle["app_secret"].encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, presented):
        raise ValidationError("Webhook signature verification failed")


def _parse_source_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


@transaction.atomic
def record_webhook_payload(
    *,
    connector: ConnectorProfile,
    payload: dict[str, Any],
) -> list[uuid.UUID]:
    require_meta_ads_entitlement(connector.company)
    if connector.status != ConnectorProfile.Status.ACTIVE:
        raise ValidationError("Meta connector is not active")
    if payload.get("object") != "page":
        return []
    configured_page = str(connector.public_config.get("page_id") or "")
    configured_forms = {str(value) for value in (connector.public_config.get("lead_form_ids") or [])}
    created_ids: list[uuid.UUID] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        page_id = str(entry.get("id") or "")
        if configured_page and page_id and page_id != configured_page:
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict) or change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            lead_id = str(value.get("leadgen_id") or value.get("lead_id") or "").strip()
            form_id = str(value.get("form_id") or "").strip()
            if not lead_id:
                continue
            if configured_forms and form_id and form_id not in configured_forms:
                continue
            metadata = {
                "lead_id": lead_id,
                "page_id": str(value.get("page_id") or page_id),
                "form_id": form_id,
                "ad_id": str(value.get("ad_id") or ""),
                "adset_id": str(value.get("adset_id") or value.get("adgroup_id") or ""),
                "campaign_id": str(value.get("campaign_id") or ""),
                "created_time": value.get("created_time"),
            }
            receipt, created = MetaLeadReceipt.objects.get_or_create(
                connector=connector,
                external_lead_id=lead_id,
                defaults={
                    "company": connector.company,
                    "page_id": metadata["page_id"],
                    "form_id": metadata["form_id"],
                    "ad_id": metadata["ad_id"],
                    "adset_id": metadata["adset_id"],
                    "campaign_id": metadata["campaign_id"],
                    "source_created_at": _parse_source_time(metadata["created_time"]),
                    "payload_digest_sha256": _digest(metadata),
                },
            )
            if created:
                receipt.full_clean()
                receipt.save()
                created_ids.append(receipt.public_id)
    return created_ids


def _graph_json(
    *,
    connector: ConnectorProfile,
    resource: str,
    fields: list[str],
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    bundle = _secret_bundle(connector)
    version = _graph_version(connector)
    base = connector.base_url.rstrip("/")
    if base != "https://graph.facebook.com":
        raise ValidationError("Meta Graph base URL must be https://graph.facebook.com")
    query = urllib.parse.urlencode({
        "fields": ",".join(fields),
        "access_token": bundle["page_access_token"],
    })
    url = f"{base}/{version}/{urllib.parse.quote(resource, safe='')}?{query}"
    request = urllib.request.Request(  # noqa: S310 -- exact HTTPS Meta Graph host validated above
        url, headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 -- request URL is pinned to Meta Graph HTTPS
            request, timeout=timeout_seconds
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        detail = ""
        try:
            body = json.loads(raw.decode("utf-8"))
            detail = str((body.get("error") or {}).get("message") or "")
        except Exception:
            detail = ""
        raise ValidationError(f"Meta Graph request failed ({exc.code})" + (f": {detail[:200]}" if detail else "")) from exc
    except urllib.error.URLError as exc:
        raise ValidationError("Meta Graph endpoint is unavailable") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Meta Graph response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValidationError("Meta Graph response was not an object")
    if data.get("error"):
        message = str((data.get("error") or {}).get("message") or "Meta Graph returned an error")
        raise ValidationError(message[:300])
    return data


def test_meta_connection(connector: ConnectorProfile) -> dict[str, Any]:
    _connector_contract(connector, resolve_secret=True)
    result = _graph_json(
        connector=connector,
        resource=str(connector.public_config["page_id"]),
        fields=["id", "name"],
    )
    if str(result.get("id") or "") != str(connector.public_config["page_id"]):
        raise ValidationError("Meta page response did not match the configured Page ID")
    return {"page_id": str(result.get("id") or ""), "page_name": str(result.get("name") or "")}


def _field_values(payload: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for row in payload.get("field_data") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        values = row.get("values") or []
        if name and isinstance(values, list):
            output[name] = str(values[0]) if values else ""
    return output


def _published_mapping(connector: ConnectorProfile) -> list[dict[str, Any]]:
    code = str(connector.public_config.get("mapping_code") or DEFAULT_MAPPING_CODE)
    mapping = (
        DataMappingProfile.objects.filter(
            connector=connector,
            code=code,
            status=DataMappingProfile.Status.PUBLISHED,
        )
        .order_by("-version")
        .first()
    )
    if mapping is None:
        raise ValidationError("A published Meta Lead Ads data mapping is required")
    return list(mapping.mappings or [])


def _apply_mapping(values: dict[str, str], mappings: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "first_name": "",
        "last_name": "",
        "full_name": "",
        "email": "",
        "phone": "",
        "job_title": "",
        "company_name": "",
        "address": {},
        "custom": {},
    }
    for row in mappings:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        target = str(row.get("target") or "")
        value = values.get(source, "").strip()
        if not value:
            continue
        if target == "contact.first_name":
            result["first_name"] = value
        elif target == "contact.last_name":
            result["last_name"] = value
        elif target == "contact.full_name":
            result["full_name"] = value
        elif target == "contact.email":
            result["email"] = value
        elif target == "contact.phone":
            result["phone"] = value
        elif target == "contact.job_title":
            result["job_title"] = value
        elif target == "lead.company_name":
            result["company_name"] = value
        elif target.startswith("contact.address."):
            result["address"][target.removeprefix("contact.address.")] = value
        elif target.startswith("contact.custom."):
            result["custom"][target.removeprefix("contact.custom.")] = value
    if result["full_name"] and not result["first_name"]:
        parts = str(result["full_name"]).split(maxsplit=1)
        result["first_name"] = parts[0]
        if len(parts) > 1 and not result["last_name"]:
            result["last_name"] = parts[1]
    return result


def _crm_actor(owner: Membership) -> CrmRequestActor:
    return CrmRequestActor(
        user_public_id=owner.user.public_id,
        membership_public_id=owner.public_id,
        request_id=uuid.uuid4(),
        ip_address=None,
        user_agent="Build360 Meta Lead Ads worker",
    )


def _meta_source_code(platform: Any) -> str:
    value = str(platform or "").strip().lower()
    if value in {"ig", "instagram", "instagram_direct"}:
        return META_SOURCE_INSTAGRAM
    if value in {"fb", "facebook", "facebook_direct"}:
        return META_SOURCE_FACEBOOK
    return META_SOURCE_CODE


def _meta_source_label(source_code: str) -> str:
    if source_code == META_SOURCE_INSTAGRAM:
        return "Instagram"
    if source_code == META_SOURCE_FACEBOOK:
        return "Facebook"
    return "Meta Ads"


def _submitted_answers(values: dict[str, str]) -> dict[str, str]:
    protected = {
        "first_name", "last_name", "full_name", "name",
        "email", "email_address", "work_email",
        "phone", "phone_number", "mobile", "mobile_number", "telephone",
    }
    output: dict[str, str] = {}
    for key, value in values.items():
        normalized = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
        if not normalized or normalized in protected:
            continue
        text = str(value or "").strip()
        if text:
            output[str(key)[:160]] = text[:2000]
    return output


def _metadata(receipt: MetaLeadReceipt, fetched: dict[str, Any]) -> dict[str, str]:
    source_code = _meta_source_code(fetched.get("platform"))
    return {
        "lead_id": receipt.external_lead_id,
        "page_id": str(fetched.get("page_id") or receipt.page_id or ""),
        "form_id": str(fetched.get("form_id") or receipt.form_id or ""),
        "campaign_id": str(fetched.get("campaign_id") or receipt.campaign_id or ""),
        "campaign_name": str(fetched.get("campaign_name") or ""),
        "adset_id": str(fetched.get("adset_id") or receipt.adset_id or ""),
        "adset_name": str(fetched.get("adset_name") or ""),
        "ad_id": str(fetched.get("ad_id") or receipt.ad_id or ""),
        "ad_name": str(fetched.get("ad_name") or ""),
        "platform": str(fetched.get("platform") or ""),
        "source_code": source_code,
        "source_label": _meta_source_label(source_code),
    }


def process_meta_lead_receipt(receipt_public_id: uuid.UUID) -> MetaLeadReceipt:
    receipt = (
        MetaLeadReceipt.objects.select_related("connector", "company")
        .filter(public_id=receipt_public_id)
        .first()
    )
    if receipt is None:
        raise ValidationError("Meta lead receipt was not found")
    connector = receipt.connector
    _connector_contract(connector, resolve_secret=True)

    MetaLeadReceipt.objects.filter(pk=receipt.pk).update(
        status=MetaLeadReceipt.Status.PROCESSING,
        attempt_count=receipt.attempt_count + 1,
        last_attempt_at=timezone.now(),
        error_summary="",
    )

    try:
        fetched = _graph_json(
            connector=connector,
            resource=receipt.external_lead_id,
            fields=[
                "created_time",
                "field_data",
                "form_id",
                "ad_id",
                "adset_id",
                "campaign_id",
                "campaign_name",
                "adset_name",
                "ad_name",
                "platform",
            ],
        )
        values = _field_values(fetched)
        mapped = _apply_mapping(values, _published_mapping(connector))
        email = str(mapped["email"])
        phone = str(mapped["phone"])
        if not email and not phone:
            raise ValidationError("Mapped Meta lead must contain an email or phone number")
        owner = _config_owner(connector)
        actor = _crm_actor(owner)
        duplicates = (
            contact_duplicates(company=connector.company, email=email, phone=phone)
            .select_related("customer")
            .order_by("-created_at")
        )
        contact: Contact | None = duplicates.first()
        new_contact = contact is None
        meta = _metadata(receipt, fetched)
        source_code = meta["source_code"]
        if source_code == META_SOURCE_CODE and contact is not None and contact.source_code in {META_SOURCE_FACEBOOK, META_SOURCE_INSTAGRAM}:
            source_code = contact.source_code
            meta["source_code"] = source_code
            meta["source_label"] = _meta_source_label(source_code)
        source_label = meta["source_label"]
        source_tag = f"meta-source:{source_code.lower()}"
        if contact is None:
            first_name = str(mapped["first_name"] or "").strip() or "Meta"
            contact = create_contact(
                company=connector.company,
                actor=actor,
                first_name=first_name,
                last_name=str(mapped["last_name"] or ""),
                job_title=str(mapped["job_title"] or ""),
                email=email,
                phone=phone,
                source_code=source_code,
                address=dict(mapped["address"]),
                tags=["meta-ads", source_tag],
                custom_fields=dict(mapped["custom"]),
                owner_membership_public_id=owner.public_id,
            )
        else:
            tags = sorted({*(contact.tags or []), "meta-ads", source_tag})
            changed = contact.source_code != source_code or tags != list(contact.tags or [])
            if changed:
                before_source = contact.source_code
                contact.source_code = source_code
                contact.tags = tags
                contact.version += 1
                contact.full_clean()
                contact.save(update_fields=["source_code", "tags", "version", "updated_at"])
                _audit(
                    actor=actor,
                    company=connector.company,
                    action="integration.meta_leads.contact_source_refreshed",
                    entity_type="crm_contact",
                    entity_public_id=contact.public_id,
                    after={"before_source": before_source, "source_code": source_code},
                )

        display_name = " ".join(
            value for value in [contact.first_name, contact.last_name] if value
        ).strip() or "Meta contact"
        now = timezone.now()
        create_activity(
            company=connector.company,
            actor=actor,
            activity_type=Activity.ActivityType.CALL,
            status=Activity.Status.PLANNED,
            direction=Activity.Direction.OUTBOUND,
            priority=Activity.Priority.HIGH,
            subject=f"Call {display_name} · New {source_label} enquiry",
            notes=(
                f"New person/enquiry received from {source_label} Lead Ads. "
                "Review the submitted ad details below before calling."
            ),
            contact=contact,
            scheduled_for=now + timedelta(minutes=5),
            channel_metadata={
                "provider": META_ACTIVITY_PROVIDER,
                **meta,
                "submitted_answers": _submitted_answers(values),
            },
            owner_membership_public_id=owner.public_id,
        )

        receipt = MetaLeadReceipt.objects.get(pk=receipt.pk)
        receipt.page_id = str(fetched.get("page_id") or receipt.page_id or "")
        receipt.form_id = str(fetched.get("form_id") or receipt.form_id or "")
        receipt.ad_id = str(fetched.get("ad_id") or receipt.ad_id or "")
        receipt.adset_id = str(fetched.get("adset_id") or receipt.adset_id or "")
        receipt.campaign_id = str(fetched.get("campaign_id") or receipt.campaign_id or "")
        receipt.source_created_at = _parse_source_time(fetched.get("created_time")) or receipt.source_created_at
        receipt.field_names = sorted(values)
        receipt.contact_public_id = contact.public_id
        receipt.lead_public_id = None
        receipt.status = (
            MetaLeadReceipt.Status.PROCESSED
            if new_contact
            else MetaLeadReceipt.Status.DUPLICATE
        )
        receipt.processed_at = timezone.now()
        receipt.error_summary = ""
        receipt.full_clean()
        receipt.save()
        return receipt
    except Exception as exc:
        receipt = MetaLeadReceipt.objects.get(pk=receipt.pk)
        receipt.status = MetaLeadReceipt.Status.FAILED
        if isinstance(exc, ValidationError):
            detail = "; ".join(str(item) for item in exc.messages)
        else:
            detail = str(exc)
        receipt.error_summary = detail[:500]
        receipt.save(update_fields=["status", "error_summary", "updated_at"])
        return receipt


@transaction.atomic
def activate_meta_connector(
    *,
    company: Company,
    actor: RequestActor,
    connector_public_id: uuid.UUID,
    expected_version: int,
    target_status: str,
) -> ConnectorProfile:
    connector = ConnectorProfile.objects.filter(
        company=company,
        public_id=connector_public_id,
        provider_code=META_PROVIDER_CODE,
    ).first()
    if connector is None:
        raise ValidationError("Meta connector was not found")
    require_meta_ads_entitlement(company)
    if target_status == ConnectorProfile.Status.ACTIVE:
        _connector_contract(connector, resolve_secret=True)
    return transition_connector_status(
        company=company,
        actor=actor,
        public_id=connector.public_id,
        expected_version=expected_version,
        target_status=target_status,
        reason="meta_lead_ads_configuration",
    )


def meta_receipt_payload(receipt: MetaLeadReceipt) -> dict[str, Any]:
    return {
        "public_id": str(receipt.public_id),
        "connector_public_id": str(receipt.connector.public_id),
        "external_lead_id": receipt.external_lead_id,
        "page_id": receipt.page_id,
        "form_id": receipt.form_id,
        "campaign_id": receipt.campaign_id,
        "adset_id": receipt.adset_id,
        "ad_id": receipt.ad_id,
        "source_created_at": receipt.source_created_at,
        "field_names": receipt.field_names,
        "status": receipt.status,
        "contact_public_id": str(receipt.contact_public_id) if receipt.contact_public_id else None,
        "lead_public_id": str(receipt.lead_public_id) if receipt.lead_public_id else None,
        "attempt_count": receipt.attempt_count,
        "last_attempt_at": receipt.last_attempt_at,
        "processed_at": receipt.processed_at,
        "error_summary": receipt.error_summary,
        "created_at": receipt.created_at,
    }
