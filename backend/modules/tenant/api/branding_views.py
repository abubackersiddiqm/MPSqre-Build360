from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.platform.actors import request_actor
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.api.base import TenantScopedAPIView
from modules.tenant.api.branding_serializers import (
    BrandingAssetAttachSerializer,
    BrandingUpdateSerializer,
    DomainActionSerializer,
    DomainCreateSerializer,
)
from modules.tenant.models import CompanyBrandProfile, CompanyEmailDeliveryProfile, TenantDomain


def _require_feature(company, code: str) -> None:
    if not feature_enabled(company=company, code=code):
        raise PermissionDenied("This tenant experience capability is disabled for the company subscription")


def _validation(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)


def _branding(profile: CompanyBrandProfile) -> dict[str, object]:
    return {
        "public_id": str(profile.public_id),
        "product_name": profile.product_name,
        "tagline": profile.tagline,
        "logo_url": "/api/public-brand-assets/logo" if profile.logo_file_public_id else profile.logo_url,
        "logo_file_public_id": str(profile.logo_file_public_id) if profile.logo_file_public_id else None,
        "compact_logo_url": "/api/public-brand-assets/compact_logo" if profile.compact_logo_file_public_id else profile.compact_logo_url,
        "compact_logo_file_public_id": str(profile.compact_logo_file_public_id) if profile.compact_logo_file_public_id else None,
        "favicon_url": "/api/public-brand-assets/favicon" if profile.favicon_file_public_id else profile.favicon_url,
        "favicon_file_public_id": str(profile.favicon_file_public_id) if profile.favicon_file_public_id else None,
        "login_background_url": "/api/public-brand-assets/login_background" if profile.login_background_file_public_id else profile.login_background_url,
        "login_background_file_public_id": str(profile.login_background_file_public_id) if profile.login_background_file_public_id else None,
        "primary_color": profile.primary_color,
        "accent_color": profile.accent_color,
        "sidebar_style": profile.sidebar_style,
        "sender_name": profile.sender_name,
        "support_email": profile.support_email,
        "document_footer": profile.document_footer,
        "powered_by_build360": profile.powered_by_build360,
        "version": profile.version,
    }


def _public_branding(profile: CompanyBrandProfile) -> dict[str, object]:
    return {
        "product_name": profile.product_name,
        "tagline": profile.tagline,
        "logo_url": "/api/public-brand-assets/logo" if profile.logo_file_public_id else profile.logo_url,
        "logo_file_public_id": str(profile.logo_file_public_id) if profile.logo_file_public_id else None,
        "compact_logo_url": "/api/public-brand-assets/compact_logo" if profile.compact_logo_file_public_id else profile.compact_logo_url,
        "compact_logo_file_public_id": str(profile.compact_logo_file_public_id) if profile.compact_logo_file_public_id else None,
        "favicon_url": "/api/public-brand-assets/favicon" if profile.favicon_file_public_id else profile.favicon_url,
        "favicon_file_public_id": str(profile.favicon_file_public_id) if profile.favicon_file_public_id else None,
        "login_background_url": "/api/public-brand-assets/login_background" if profile.login_background_file_public_id else profile.login_background_url,
        "login_background_file_public_id": str(profile.login_background_file_public_id) if profile.login_background_file_public_id else None,
        "primary_color": profile.primary_color,
        "accent_color": profile.accent_color,
        "sidebar_style": profile.sidebar_style,
        "powered_by_build360": profile.powered_by_build360,
        "version": profile.version,
    }


def _domain(item: TenantDomain) -> dict[str, object]:
    return {
        "public_id": str(item.public_id),
        "domain": item.domain,
        "domain_type": item.domain_type,
        "status": item.status,
        "is_primary": item.is_primary,
        "verification_record_name": item.verification_record_name,
        "verification_record_value": item.verification_record_value,
        "expected_cname": item.expected_cname,
        "verified_at": item.verified_at,
        "ssl_status": item.ssl_status,
        "activated_at": item.activated_at,
        "version": item.version,
    }


def _profile_defaults(company) -> dict[str, object]:
    return {
        "product_name": company.display_name,
        "tagline": "Construction Operating System",
        "sender_name": company.display_name,
    }


def _profile(company) -> CompanyBrandProfile:
    profile, _ = CompanyBrandProfile.objects.get_or_create(
        company=company,
        defaults=_profile_defaults(company),
    )
    return profile


class CurrentBrandingView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.read")
        _require_feature(self.tenant_context.company, "tenant.white_label")
        return Response(_branding(_profile(self.tenant_context.company)))

    def patch(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.manage")
        _require_feature(self.tenant_context.company, "tenant.white_label")
        serializer = BrandingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        expected_version = data.pop("expected_version")
        actor = request_actor(request, self.tenant_context)
        try:
            with transaction.atomic():
                profile, _ = CompanyBrandProfile.objects.select_for_update().get_or_create(
                    company=self.tenant_context.company,
                    defaults=_profile_defaults(self.tenant_context.company),
                )
                if profile.version != expected_version:
                    raise ValidationError(
                        {"expected_version": ["Branding changed in another session. Refresh and retry."]}
                    )
                for key, value in data.items():
                    setattr(profile, key, value)
                profile.updated_by_public_id = actor.user_public_id
                profile.version += 1
                profile.full_clean()
                profile.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_branding(profile))


class CurrentDomainListCreateView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("tenant.domain.read")
        _require_feature(self.tenant_context.company, "tenant.custom_domain")
        items = TenantDomain.objects.filter(company=self.tenant_context.company)
        return Response(
            {
                "items": [_domain(item) for item in items],
                "platform_domain_suffix": getattr(settings, "BUILD360_PLATFORM_DOMAIN_SUFFIX", ""),
                "custom_domain_cname_target": getattr(
                    settings, "BUILD360_CUSTOM_DOMAIN_CNAME_TARGET", ""
                ),
            }
        )

    def post(self, request: Request) -> Response:
        self.tenant_context.require("tenant.domain.manage")
        _require_feature(self.tenant_context.company, "tenant.custom_domain")
        serializer = DomainCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        domain = data["domain"].strip().lower().rstrip(".")
        domain_type = data["domain_type"]
        make_primary = data["make_primary"]
        suffix = getattr(settings, "BUILD360_PLATFORM_DOMAIN_SUFFIX", "").strip().lower().strip(".")
        cname = getattr(settings, "BUILD360_CUSTOM_DOMAIN_CNAME_TARGET", "").strip().lower().rstrip(".")

        if domain_type == TenantDomain.DomainType.PLATFORM_SUBDOMAIN:
            if not suffix:
                raise ValidationError({"domain": ["Platform domain suffix is not configured."]})
            expected = f"{self.tenant_context.company.code.lower()}.{suffix}"
            if domain != expected:
                raise ValidationError(
                    {"domain": [f"This company platform subdomain is {expected}."]}
                )

        token = secrets.token_urlsafe(32)
        try:
            with transaction.atomic():
                activates_immediately = domain_type == TenantDomain.DomainType.PLATFORM_SUBDOMAIN
                set_primary = bool(make_primary and activates_immediately)
                if set_primary:
                    TenantDomain.objects.filter(
                        company=self.tenant_context.company, is_primary=True
                    ).update(is_primary=False, version=models.F("version") + 1)
                item = TenantDomain(
                    company=self.tenant_context.company,
                    domain=domain,
                    domain_type=domain_type,
                    is_primary=set_primary,
                    verification_token=token,
                    verification_record_name=f"_build360-verify.{domain}",
                    verification_record_value=f"build360-verification={token}",
                    expected_cname=cname,
                )
                if domain_type == TenantDomain.DomainType.PLATFORM_SUBDOMAIN:
                    item.status = TenantDomain.Status.ACTIVE
                    item.verified_at = timezone.now()
                    item.activated_at = timezone.now()
                    item.ssl_status = TenantDomain.SslStatus.PENDING
                item.full_clean()
                item.save()
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        except IntegrityError as exc:
            raise ValidationError({"domain": ["That domain is already registered."]}) from exc
        return Response(_domain(item), status=201)


class DomainVerifyView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("tenant.domain.manage")
        _require_feature(self.tenant_context.company, "tenant.custom_domain")
        serializer = DomainActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                item = TenantDomain.objects.select_for_update().filter(
                    company=self.tenant_context.company,
                    public_id=public_id,
                ).first()
                if item is None:
                    raise NotFound("Resource not found")
                if item.version != serializer.validated_data["expected_version"]:
                    raise ValidationError(
                        {"expected_version": ["Domain changed in another session. Refresh and retry."]}
                    )
                if item.domain_type == TenantDomain.DomainType.PLATFORM_SUBDOMAIN:
                    item.status = TenantDomain.Status.ACTIVE
                    item.verified_at = item.verified_at or timezone.now()
                    item.activated_at = item.activated_at or timezone.now()
                    item.version += 1
                    item.save(update_fields=["status", "verified_at", "activated_at", "version", "updated_at"])
                else:
                    return Response(
                        {
                            **_domain(item),
                            "verification_required": True,
                            "message": "Custom-domain DNS must be verified by the deployment operator before activation.",
                        }
                    )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(_domain(item))


class DomainPrimaryView(TenantScopedAPIView):
    def post(self, request: Request, public_id: uuid.UUID) -> Response:
        self.tenant_context.require("tenant.domain.manage")
        _require_feature(self.tenant_context.company, "tenant.custom_domain")
        serializer = DomainActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            item = TenantDomain.objects.select_for_update().filter(
                company=self.tenant_context.company,
                public_id=public_id,
            ).first()
            if item is None:
                raise NotFound("Resource not found")
            if item.version != serializer.validated_data["expected_version"]:
                raise ValidationError(
                    {"expected_version": ["Domain changed in another session. Refresh and retry."]}
                )
            if item.status != TenantDomain.Status.ACTIVE:
                raise ValidationError({"domain": ["Only an active domain can become primary."]})
            TenantDomain.objects.filter(
                company=self.tenant_context.company, is_primary=True
            ).exclude(pk=item.pk).update(is_primary=False, version=models.F("version") + 1)
            item.is_primary = True
            item.version += 1
            item.save(update_fields=["is_primary", "version", "updated_at"])
        return Response(_domain(item))


class PublicDomainResolveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        host = request.query_params.get("host", "").strip().lower().split(":", 1)[0].rstrip(".")
        if not host:
            raise ValidationError({"host": ["Host is required."]})
        item = TenantDomain.objects.select_related("company").filter(
            domain=host,
            status=TenantDomain.Status.ACTIVE,
            company__is_active=True,
        ).first()
        if item is None:
            raise NotFound("Domain is not mapped to an active company")
        if item.domain_type == TenantDomain.DomainType.CUSTOM_DOMAIN and not feature_enabled(
            company=item.company, code="tenant.custom_domain"
        ):
            raise NotFound("Domain is not mapped to an active company")
        profile = CompanyBrandProfile.objects.filter(company=item.company).first()
        white_label_enabled = feature_enabled(company=item.company, code="tenant.white_label")
        branding = (
            _public_branding(profile)
            if profile is not None and white_label_enabled
            else {
                **_profile_defaults(item.company),
                "logo_url": "",
                "compact_logo_url": "",
                "favicon_url": "",
                "login_background_url": "",
                "primary_color": "#174D3C",
                "accent_color": "#0F766E",
                "sidebar_style": CompanyBrandProfile.SidebarStyle.LIGHT,
                "powered_by_build360": True,
                "version": 1,
            }
        )
        return Response(
            {
                "company": {
                    "public_id": str(item.company.public_id),
                    "code": item.company.code,
                    "display_name": item.company.display_name,
                },
                "domain": {
                    "domain": item.domain,
                    "domain_type": item.domain_type,
                    "is_primary": item.is_primary,
                    "ssl_status": item.ssl_status,
                },
                "branding": branding,
            }
        )


_BRAND_ASSET_SLOTS = {
    "logo": ("logo_file_public_id", "tenant.brand.logo", {"image/png", "image/jpeg", "image/webp"}),
    "compact_logo": ("compact_logo_file_public_id", "tenant.brand.compact_logo", {"image/png", "image/jpeg", "image/webp"}),
    "favicon": ("favicon_file_public_id", "tenant.brand.favicon", {"image/png", "image/webp"}),
    "login_background": ("login_background_file_public_id", "tenant.brand.login_background", {"image/png", "image/jpeg", "image/webp"}),
}


def _brand_asset_candidate(file_object) -> dict[str, object]:
    version = file_object.versions.order_by("-version").first()
    return {
        "file_public_id": str(file_object.public_id),
        "purpose_code": file_object.purpose_code,
        "original_name": version.original_name if version else "",
        "content_type": version.content_type if version else "",
        "upload_status": version.upload_status if version else "",
        "scan_status": version.scan_status if version else "",
        "created_at": version.created_at if version else file_object.created_at,
    }


class CurrentBrandingAssetListView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.read")
        _require_feature(self.tenant_context.company, "tenant.white_label")
        from modules.files.models import FileObject

        purposes = [value[1] for value in _BRAND_ASSET_SLOTS.values()]
        items = (
            FileObject.objects.filter(
                company=self.tenant_context.company,
                purpose_code__in=purposes,
            )
            .prefetch_related("versions")
            .order_by("-created_at")[:80]
        )
        return Response({"items": [_brand_asset_candidate(item) for item in items]})


class CurrentBrandingAssetAttachView(TenantScopedAPIView):
    def post(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.manage")
        _require_feature(self.tenant_context.company, "tenant.white_label")
        serializer = BrandingAssetAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        slot = data["slot"]
        field_name, purpose_code, allowed_types = _BRAND_ASSET_SLOTS[slot]

        from modules.files.models import FileObject, FileVersion
        file_object = (
            FileObject.objects.prefetch_related("versions")
            .filter(
                company=self.tenant_context.company,
                public_id=data["file_public_id"],
                purpose_code=purpose_code,
                status=FileObject.Status.ACTIVE,
            )
            .first()
        )
        if file_object is None:
            raise ValidationError({"file_public_id": ["Brand asset file was not found."]})
        version = file_object.versions.order_by("-version").first()
        if version is None or version.upload_status != FileVersion.UploadStatus.FINALIZED:
            raise ValidationError({"file_public_id": ["Upload must be finalized before it can be used."]})
        if version.scan_status != FileVersion.ScanStatus.CLEAN:
            raise ValidationError({"file_public_id": ["Security scan must be clean before activation."]})
        if version.content_type not in allowed_types:
            raise ValidationError({"file_public_id": ["This image type is not supported for the selected brand slot."]})

        actor = request_actor(request, self.tenant_context)
        with transaction.atomic():
            profile, _ = CompanyBrandProfile.objects.select_for_update().get_or_create(
                company=self.tenant_context.company,
                defaults=_profile_defaults(self.tenant_context.company),
            )
            if profile.version != data["expected_version"]:
                raise ValidationError({"expected_version": ["Branding changed in another session. Refresh and retry."]})
            setattr(profile, field_name, file_object.public_id)
            profile.updated_by_public_id = actor.user_public_id
            profile.version += 1
            profile.save(update_fields=[field_name, "updated_by_public_id", "version", "updated_at"])
        return Response(_branding(profile))


class PublicBrandAssetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        host = request.query_params.get("host", "").strip().lower().split(":", 1)[0].rstrip(".")
        slot = request.query_params.get("slot", "").strip().lower()
        if slot not in _BRAND_ASSET_SLOTS:
            raise ValidationError({"slot": ["Unknown brand asset slot."]})
        if not host:
            raise ValidationError({"host": ["Host is required."]})
        domain = TenantDomain.objects.select_related("company").filter(
            domain=host,
            status=TenantDomain.Status.ACTIVE,
            company__is_active=True,
        ).first()
        if domain is None:
            raise NotFound("Domain is not mapped to an active company")
        profile = CompanyBrandProfile.objects.filter(company=domain.company).first()
        if profile is None:
            raise NotFound("Brand asset is not configured")
        field_name, _, _ = _BRAND_ASSET_SLOTS[slot]
        file_public_id = getattr(profile, field_name)
        if not file_public_id:
            raise NotFound("Brand asset is not configured")

        from modules.files.application.services import governed_download_url
        from modules.files.models import FileObject
        file_object = FileObject.objects.filter(
            company=domain.company,
            public_id=file_public_id,
            status=FileObject.Status.ACTIVE,
        ).first()
        if file_object is None:
            raise NotFound("Brand asset is not available")
        try:
            version, url = governed_download_url(file_object=file_object)
        except DjangoValidationError as exc:
            raise NotFound("Brand asset is not available") from exc
        return Response({
            "download_url": url,
            "content_type": version.content_type,
            "cache_seconds": 240,
        })


class CurrentTenantOnboardingView(TenantScopedAPIView):
    def get(self, request: Request) -> Response:
        self.tenant_context.require("tenant.branding.read")
        company = self.tenant_context.company
        profile = _profile(company)
        domains = list(TenantDomain.objects.filter(company=company))
        platform_domain = next((item for item in domains if item.domain_type == TenantDomain.DomainType.PLATFORM_SUBDOMAIN), None)
        custom_domains = [item for item in domains if item.domain_type == TenantDomain.DomainType.CUSTOM_DOMAIN]
        active_custom = next((item for item in custom_domains if item.status == TenantDomain.Status.ACTIVE), None)
        has_logo = bool(profile.logo_file_public_id or profile.logo_url)
        steps = [
            {"code": "IDENTITY", "label": "Company identity", "done": bool(profile.product_name and profile.tagline)},
            {"code": "BRAND_ASSETS", "label": "Logo / brand assets", "done": has_logo},
            {"code": "PLATFORM_DOMAIN", "label": "Build360 subdomain", "done": bool(platform_domain and platform_domain.status == TenantDomain.Status.ACTIVE)},
            {"code": "CUSTOM_DOMAIN", "label": "Custom domain", "done": bool(active_custom), "optional": True},
            {"code": "MESSAGING", "label": "Sender & support identity", "done": bool(profile.sender_name and profile.support_email)},
            {
                "code": "EMAIL_DELIVERY",
                "label": "Company email delivery",
                "done": CompanyEmailDeliveryProfile.objects.filter(
                    company=company,
                    delivery_mode=CompanyEmailDeliveryProfile.DeliveryMode.TENANT_SMTP,
                    status=CompanyEmailDeliveryProfile.Status.ACTIVE,
                    verified_at__isnull=False,
                ).exists(),
                "optional": True,
            },
        ]
        required = [step for step in steps if not step.get("optional")]
        complete = sum(1 for step in required if step["done"])
        return Response({
            "company": {"code": company.code, "display_name": company.display_name},
            "completion_percent": int(complete / len(required) * 100) if required else 100,
            "steps": steps,
            "domains": [_domain(item) for item in domains],
        })
