from __future__ import annotations

import hashlib
import json

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.identity.models import Permission, Role, RolePermission, User
from modules.integration.models import (
    ConnectorProfile,
    DataMappingProfile,
    LocalizationPack,
    WebhookSubscription,
)
from modules.notifications.models import Notification
from modules.tenant.models import Company, Membership

REGION_PACKS = [
    {
        "code": "INDIA_EN",
        "name": "India English",
        "country_code": "IN",
        "locale": "en-IN",
        "currency": "INR",
        "timezone": "Asia/Kolkata",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "number_format": {
            "decimal": ".",
            "group": ",",
            "grouping": [3, 2],
            "currency_position": "before",
        },
        "address_schema": {
            "fields": [
                "line1",
                "line2",
                "district",
                "state",
                "postal_code",
                "country",
            ]
        },
        "tax_schema": {
            "system": "GST",
            "labels": ["CGST", "SGST", "IGST"],
            "tax_identifier": "GSTIN",
        },
        "terminology": {
            "postal_code": "PIN code",
            "tax_invoice": "Tax invoice",
            "work_order": "Work order",
        },
        "published": True,
    },
    {
        "code": "UAE_EN",
        "name": "United Arab Emirates English",
        "country_code": "AE",
        "locale": "en-AE",
        "currency": "AED",
        "timezone": "Asia/Dubai",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "tax_schema": {"system": "VAT", "labels": ["VAT"], "tax_identifier": "TRN"},
    },
    {
        "code": "SAUDI_EN",
        "name": "Saudi Arabia English",
        "country_code": "SA",
        "locale": "en-SA",
        "currency": "SAR",
        "timezone": "Asia/Riyadh",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "tax_schema": {"system": "VAT", "labels": ["VAT"], "tax_identifier": "VAT number"},
    },
    {
        "code": "SINGAPORE_EN",
        "name": "Singapore English",
        "country_code": "SG",
        "locale": "en-SG",
        "currency": "SGD",
        "timezone": "Asia/Singapore",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "tax_schema": {"system": "GST", "labels": ["GST"], "tax_identifier": "GST registration"},
    },
    {
        "code": "AUSTRALIA_EN",
        "name": "Australia English",
        "country_code": "AU",
        "locale": "en-AU",
        "currency": "AUD",
        "timezone": "Australia/Sydney",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "tax_schema": {"system": "GST", "labels": ["GST"], "tax_identifier": "ABN"},
    },
    {
        "code": "UK_EN",
        "name": "United Kingdom English",
        "country_code": "GB",
        "locale": "en-GB",
        "currency": "GBP",
        "timezone": "Europe/London",
        "unit_system_code": "metric",
        "date_format": "DD/MM/YYYY",
        "tax_schema": {"system": "VAT", "labels": ["VAT"], "tax_identifier": "VAT registration"},
    },
    {
        "code": "USA_EN",
        "name": "United States English",
        "country_code": "US",
        "locale": "en-US",
        "currency": "USD",
        "timezone": "America/New_York",
        "unit_system_code": "imperial",
        "date_format": "MM/DD/YYYY",
        "tax_schema": {"system": "SALES_TAX", "labels": ["Sales tax"], "tax_identifier": "Tax ID"},
    },
    {
        "code": "CANADA_EN",
        "name": "Canada English",
        "country_code": "CA",
        "locale": "en-CA",
        "currency": "CAD",
        "timezone": "America/Toronto",
        "unit_system_code": "metric",
        "date_format": "YYYY-MM-DD",
        "tax_schema": {
            "system": "GST_HST",
            "labels": ["GST", "HST", "PST"],
            "tax_identifier": "Business number",
        },
    },
]


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Initialize Phase 14 globalization and integration-hub controls."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--admin-email", required=True)

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        company = Company.objects.filter(
            code__iexact=str(options["company_code"]).strip(),
            is_active=True,
        ).first()
        user = User.objects.filter(
            email__iexact=str(options["admin_email"]).strip().lower(),
            is_active=True,
        ).first()
        if company is None or user is None:
            raise CommandError("Active company or administrator was not found")
        membership = Membership.objects.filter(
            company=company,
            user=user,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        ).first()
        if membership is None:
            raise CommandError("Administrator has no active company membership")

        now = timezone.now()
        published_count = 0
        for definition in REGION_PACKS:
            is_published = bool(definition.get("published", False))
            evidence = {
                **definition,
                "number_format": definition.get(
                    "number_format",
                    {"decimal": ".", "group": ",", "grouping": [3], "currency_position": "before"},
                ),
                "address_schema": definition.get(
                    "address_schema",
                    {"fields": ["line1", "line2", "city", "region", "postal_code", "country"]},
                ),
                "terminology": definition.get(
                    "terminology",
                    {
                        "postal_code": "Postal code",
                        "tax_invoice": "Tax invoice",
                        "work_order": "Work order",
                    },
                ),
            }
            pack, _ = LocalizationPack.objects.update_or_create(
                company=company,
                code=definition["code"],
                version=1,
                defaults={
                    "name": definition["name"],
                    "country_code": definition["country_code"],
                    "locale": definition["locale"],
                    "currency": definition["currency"],
                    "timezone": definition["timezone"],
                    "unit_system_code": definition["unit_system_code"],
                    "date_format": definition["date_format"],
                    "time_format": "24h",
                    "number_format": evidence["number_format"],
                    "address_schema": evidence["address_schema"],
                    "tax_schema": definition["tax_schema"],
                    "terminology": evidence["terminology"],
                    "status": (
                        LocalizationPack.Status.PUBLISHED
                        if is_published
                        else LocalizationPack.Status.DRAFT
                    ),
                    "is_default": is_published,
                    "effective_from": now,
                    "published_at": now if is_published else None,
                    "published_by_public_id": user.public_id if is_published else None,
                    "checksum_sha256": digest(evidence) if is_published else "",
                },
            )
            published_count += int(pack.status == LocalizationPack.Status.PUBLISHED)

        connectors = [
            {
                "code": "ACCOUNTING_PLACEHOLDER",
                "name": "Accounting connector placeholder",
                "connector_type": ConnectorProfile.ConnectorType.ACCOUNTING,
                "provider_code": "UNASSIGNED",
                "direction": ConnectorProfile.Direction.BIDIRECTIONAL,
                "public_config": {"mode": "contract-only", "external_calls_enabled": False},
                "allowed_data_classes": ["finance", "commercial"],
            },
            {
                "code": "IDENTITY_PLACEHOLDER",
                "name": "Enterprise identity connector placeholder",
                "connector_type": ConnectorProfile.ConnectorType.IDENTITY,
                "provider_code": "UNASSIGNED",
                "direction": ConnectorProfile.Direction.INBOUND,
                "public_config": {"protocols": ["OIDC", "SAML"], "external_calls_enabled": False},
                "allowed_data_classes": ["identity"],
            },
            {
                "code": "ANALYTICS_LOCAL",
                "name": "Local governed analytics export",
                "connector_type": ConnectorProfile.ConnectorType.ANALYTICS,
                "provider_code": "LOCAL",
                "direction": ConnectorProfile.Direction.OUTBOUND,
                "status": ConnectorProfile.Status.ACTIVE,
                "public_config": {"mode": "local-evidence", "external_calls_enabled": False},
                "allowed_data_classes": ["reporting", "operations"],
            },
        ]
        connector_count = 0
        for item in connectors:
            ConnectorProfile.objects.update_or_create(
                company=company,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "connector_type": item["connector_type"],
                    "provider_code": item["provider_code"],
                    "direction": item["direction"],
                    "status": item.get("status", ConnectorProfile.Status.DRAFT),
                    "public_config": item["public_config"],
                    "allowed_data_classes": item["allowed_data_classes"],
                },
            )
            connector_count += 1

        analytics = ConnectorProfile.objects.get(company=company, code="ANALYTICS_LOCAL")
        mapping, _ = DataMappingProfile.objects.update_or_create(
            connector=analytics,
            code="EXECUTIVE_METRICS",
            version=1,
            defaults={
                "name": "Executive metric export",
                "source_schema_code": "build360.reporting.metric.v1",
                "target_schema_code": "external.analytics.metric.v1",
                "mappings": [
                    {"source": "metric_code", "target": "metric_code", "required": True},
                    {"source": "value", "target": "value", "required": True},
                    {"source": "recorded_at", "target": "recorded_at", "required": True},
                ],
                "transformations": [],
                "status": DataMappingProfile.Status.PUBLISHED,
                "published_at": now,
                "published_by_public_id": user.public_id,
                "checksum_sha256": digest({"mapping": "EXECUTIVE_METRICS", "version": 1}),
            },
        )

        WebhookSubscription.objects.get_or_create(
            company=company,
            code="LOCAL_AUDIT_SAMPLE",
            defaults={
                "event_code": "integration.phase14.sample",
                "target_url": "https://example.invalid/build360-webhook",
                "status": WebhookSubscription.Status.PAUSED,
                "secret_ref": "secret://integration/local-audit-sample",
                "headers_public": {"X-Build360-Contract": "v1"},
                "allowed_data_classes": ["integration"],
            },
        )

        permissions = list(Permission.objects.filter(code__startswith="integration."))
        role_ids = membership.role_assignments.filter(effective_from__lte=now).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gt=now)
        ).values_list("role_public_id", flat=True)
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
                retired_at__isnull=True,
            )
        )
        grants = 0
        for role in roles:
            for permission in permissions:
                _, created = RolePermission.objects.get_or_create(role=role, permission=permission)
                grants += int(created)

        Notification.objects.get_or_create(
            company=company,
            user_public_id=user.public_id,
            event_code="system.phase14.ready",
            defaults={
                "title": "Phase 14 globalization and integration hub is active",
                "body": (
                    "Regional localization packs, API clients, connectors, webhooks, "
                    "data mappings and synchronization governance are ready."
                ),
                "severity": Notification.Severity.SUCCESS,
                "action_path": "/integrations",
                "source_type": "phase14_bootstrap",
            },
        )

        self.stdout.write(self.style.SUCCESS("PHASE 14 INTEGRATION INITIALIZATION COMPLETED"))
        self.stdout.write(f"Regional localization packs available: {len(REGION_PACKS)}")
        self.stdout.write(f"Published localization packs: {published_count}")
        self.stdout.write(f"Connector profiles available: {connector_count}")
        published_mappings = int(
            mapping.status == DataMappingProfile.Status.PUBLISHED
        )
        self.stdout.write(f"Published mappings available: {published_mappings}")
        self.stdout.write(f"Phase 14 permissions available: {len(permissions)}")
        self.stdout.write(f"New administrator grants: {grants}")
