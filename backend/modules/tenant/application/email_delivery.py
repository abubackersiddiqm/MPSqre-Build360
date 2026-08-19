from __future__ import annotations

import ipaddress
import logging
import socket
import ssl
import smtplib
from dataclasses import dataclass
from email.utils import formataddr

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend
from django.db.models import F, Q
from django.utils import timezone

from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import (
    Company,
    CompanyBrandProfile,
    CompanyEmailDeliveryProfile,
    Membership,
    TenantDomain,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TransactionalBrand:
    company: Company | None
    product_name: str
    sender_name: str
    support_email: str
    primary_color: str
    powered_by_build360: bool
    public_web_url: str
    logo_url: str
    white_label_enabled: bool


@dataclass(frozen=True, slots=True)
class PasswordResetScope:
    allowed: bool
    company: Company | None
    source: str


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str
    route: str
    error_code: str = ""


def _platform_web_url() -> str:
    return str(
        getattr(settings, "BUILD360_PUBLIC_WEB_URL", "http://localhost:3000")
    ).strip().rstrip("/") or "http://localhost:3000"


def _active_company_web_url(company: Company) -> str:
    custom_domain_enabled = feature_enabled(company=company, code="tenant.custom_domain")
    domains = TenantDomain.objects.filter(
        company=company,
        status=TenantDomain.Status.ACTIVE,
        ssl_status=TenantDomain.SslStatus.ACTIVE,
    ).order_by("-is_primary", "domain")
    for item in domains:
        if (
            item.domain_type == TenantDomain.DomainType.CUSTOM_DOMAIN
            and not custom_domain_enabled
        ):
            continue
        return f"https://{item.domain}"
    return _platform_web_url()


def resolve_transactional_brand(company: Company | None) -> TransactionalBrand:
    if company is None or not feature_enabled(company=company, code="tenant.white_label"):
        return TransactionalBrand(
            company=None,
            product_name="MPSqre Build360",
            sender_name="MPSqre Build360",
            support_email=str(getattr(settings, "BUILD360_SUPPORT_EMAIL", "")).strip(),
            primary_color="#174D3C",
            powered_by_build360=True,
            public_web_url=_platform_web_url(),
            logo_url="",
            white_label_enabled=False,
        )

    profile, _ = CompanyBrandProfile.objects.get_or_create(
        company=company,
        defaults={
            "product_name": company.display_name,
            "tagline": "Construction Operating System",
            "sender_name": company.display_name,
        },
    )
    product_name = profile.product_name.strip() or company.display_name
    sender_name = profile.sender_name.strip() or product_name
    public_web_url = _active_company_web_url(company)
    logo_url = profile.logo_url.strip()
    if profile.logo_file_public_id and public_web_url.startswith("https://"):
        logo_url = f"{public_web_url}/api/public-brand-assets/logo"
    return TransactionalBrand(
        company=company,
        product_name=product_name,
        sender_name=sender_name,
        support_email=profile.support_email.strip(),
        primary_color=profile.primary_color,
        powered_by_build360=profile.powered_by_build360,
        public_web_url=public_web_url,
        logo_url=logo_url,
        white_label_enabled=True,
    )


def _credential_keys() -> list[str]:
    configured = list(getattr(settings, "TENANT_EMAIL_CREDENTIAL_KEYS", []) or [])
    if configured:
        return configured
    # Non-production compatibility only. Production settings require the dedicated key ring.
    if getattr(settings, "BUILD360_ENVIRONMENT", "development") != "production":
        return list(getattr(settings, "CRM_PROTECTED_DATA_KEYS", []) or [])
    raise ImproperlyConfigured("TENANT_EMAIL_CREDENTIAL_KEYS is required in production")


def _protector() -> MultiFernet:
    try:
        return MultiFernet([Fernet(key.encode("ascii")) for key in _credential_keys()])
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            "TENANT_EMAIL_CREDENTIAL_KEYS contains an invalid Fernet key"
        ) from exc


def encrypt_smtp_password(value: str) -> str:
    if not value:
        return ""
    return _protector().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_smtp_password(value: str) -> str:
    if not value:
        return ""
    try:
        return _protector().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("Company SMTP credential could not be decrypted") from exc


def _normalize_host(value: str) -> str:
    return (value or "").strip().lower().split(":", 1)[0].rstrip(".")


def _active_membership_exists(*, user, company: Company) -> bool:
    now = timezone.now()
    return (
        Membership.objects.filter(
            company=company,
            user=user,
            company__is_active=True,
            user__is_active=True,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .exists()
    )


def resolve_password_reset_scope(*, user, public_host: str) -> PasswordResetScope:
    host = _normalize_host(public_host)
    if host:
        domain = (
            TenantDomain.objects.select_related("company")
            .filter(
                domain=host,
                status=TenantDomain.Status.ACTIVE,
                company__is_active=True,
            )
            .first()
        )
        if domain is not None:
            if not _active_membership_exists(user=user, company=domain.company):
                return PasswordResetScope(
                    allowed=False,
                    company=None,
                    source="TENANT_HOST_MEMBERSHIP_MISMATCH",
                )
            if feature_enabled(company=domain.company, code="tenant.white_label"):
                return PasswordResetScope(
                    allowed=True,
                    company=domain.company,
                    source="TENANT_HOST",
                )
            return PasswordResetScope(allowed=True, company=None, source="PLATFORM_BRAND")

    # On the shared platform domain, do not arbitrarily choose between multiple tenants.
    now = timezone.now()
    memberships = list(
        Membership.objects.select_related("company")
        .filter(
            user=user,
            user__is_active=True,
            company__is_active=True,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))[:3]
    )
    if len(memberships) == 1:
        company = memberships[0].company
        if feature_enabled(company=company, code="tenant.white_label"):
            return PasswordResetScope(
                allowed=True,
                company=company,
                source="SINGLE_TENANT_MEMBERSHIP",
            )
    return PasswordResetScope(allowed=True, company=None, source="PLATFORM")


def _reject_unsafe_smtp_destination(host: str, port: int) -> None:
    environment = getattr(settings, "BUILD360_ENVIRONMENT", "development")
    if environment != "production":
        return
    if port not in {465, 587, 2525}:
        raise ValidationError("Production company SMTP port must be 465, 587 or 2525")
    normalized = _normalize_host(host)
    if not normalized or normalized in {"localhost", "localhost.localdomain"}:
        raise ValidationError("Production company SMTP must use a public hostname")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(normalized, port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise ValidationError("Company SMTP hostname could not be resolved") from exc
    if not addresses:
        raise ValidationError("Company SMTP hostname could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_reserved,
                ip.is_multicast,
                ip.is_unspecified,
            )
        ):
            raise ValidationError("Production company SMTP cannot resolve to a private or reserved address")


def _smtp_connection(profile: CompanyEmailDeliveryProfile) -> EmailBackend:
    _reject_unsafe_smtp_destination(profile.smtp_host, profile.smtp_port)
    return EmailBackend(
        host=profile.smtp_host,
        port=profile.smtp_port,
        username=profile.smtp_username or None,
        password=decrypt_smtp_password(profile.smtp_password_encrypted) or None,
        use_tls=profile.smtp_use_tls,
        use_ssl=profile.smtp_use_ssl,
        timeout=12,
        fail_silently=False,
    )


def active_company_smtp(company: Company | None) -> CompanyEmailDeliveryProfile | None:
    if company is None or not feature_enabled(company=company, code="tenant.white_label"):
        return None
    return CompanyEmailDeliveryProfile.objects.filter(
        company=company,
        delivery_mode=CompanyEmailDeliveryProfile.DeliveryMode.TENANT_SMTP,
        status=CompanyEmailDeliveryProfile.Status.ACTIVE,
        verified_at__isnull=False,
    ).first()


def _platform_from_email(sender_name: str) -> str:
    address = str(
        getattr(settings, "BUILD360_TRANSACTIONAL_FROM_EMAIL", "notifications@mpsqre.com")
    ).strip()
    return formataddr((sender_name, address))


def _mark_tenant_delivery_failed(
    profile: CompanyEmailDeliveryProfile,
    *,
    error_code: str,
) -> None:
    try:
        CompanyEmailDeliveryProfile.objects.filter(pk=profile.pk).update(
            status=CompanyEmailDeliveryProfile.Status.FAILED,
            last_error_code=error_code[:120],
            last_tested_at=timezone.now(),
            verified_at=None,
            version=F("version") + 1,
        )
    except Exception:
        logger.exception("Could not mark tenant SMTP route failed")


def send_transactional_email(
    *,
    company: Company | None,
    subject: str,
    text: str,
    html: str,
    to: list[str],
    sender_name: str | None = None,
    reply_to: list[str] | None = None,
) -> DeliveryResult:
    brand = resolve_transactional_brand(company)
    effective_sender = (sender_name or brand.sender_name or brand.product_name).strip()
    effective_reply_to = reply_to or ([brand.support_email] if brand.support_email else None)
    profile = active_company_smtp(company)
    tenant_route_failed = False

    if profile is not None:
        try:
            connection = _smtp_connection(profile)
            message = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=formataddr((effective_sender, profile.from_email)),
                to=to,
                reply_to=effective_reply_to,
                connection=connection,
            )
            message.attach_alternative(html, "text/html")
            if message.send(fail_silently=False):
                return DeliveryResult(status="SENT", route="TENANT_SMTP")
            raise RuntimeError("backend_returned_zero")
        except Exception as exc:
            error_code = exc.__class__.__name__[:120]
            tenant_route_failed = True
            _mark_tenant_delivery_failed(profile, error_code=error_code)
            logger.warning(
                "Tenant SMTP failed; using platform transactional fallback",
                extra={
                    "company_public_id": str(company.public_id) if company else None,
                    "error_code": error_code,
                },
            )

    try:
        connection = get_connection(fail_silently=False)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=_platform_from_email(effective_sender),
            to=to,
            reply_to=effective_reply_to,
            connection=connection,
        )
        message.attach_alternative(html, "text/html")
        sent_count = message.send(fail_silently=False)
        backend_name = str(getattr(settings, "EMAIL_BACKEND", ""))
        fallback_route = "PLATFORM_FALLBACK" if tenant_route_failed else "PLATFORM"
        if "console.EmailBackend" in backend_name or "locmem.EmailBackend" in backend_name:
            return DeliveryResult(status="LOCAL_PREVIEW", route=fallback_route)
        if sent_count:
            return DeliveryResult(status="SENT", route=fallback_route)
        return DeliveryResult(
            status="FAILED",
            route="PLATFORM_FALLBACK" if tenant_route_failed else "PLATFORM",
            error_code="backend_returned_zero",
        )
    except Exception as exc:
        return DeliveryResult(
            status="FAILED",
            route="PLATFORM_FALLBACK" if tenant_route_failed else "PLATFORM",
            error_code=exc.__class__.__name__[:120],
        )


def test_company_smtp(
    *,
    profile: CompanyEmailDeliveryProfile,
    recipient: str,
    sender_name: str,
) -> DeliveryResult:
    if profile.delivery_mode != CompanyEmailDeliveryProfile.DeliveryMode.TENANT_SMTP:
        return DeliveryResult(
            status="FAILED",
            route="TENANT_SMTP",
            error_code="tenant_smtp_not_enabled",
        )
    try:
        connection = _smtp_connection(profile)
        from_email = formataddr((sender_name.strip() or "Build360", profile.from_email))
        subject = "Build360 company email connection test"
        text = (
            "This message confirms that your company SMTP connection can send "
            "Build360 transactional email.\n"
        )
        html = (
            "<p>This message confirms that your company SMTP connection can send "
            "Build360 transactional email.</p>"
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=from_email,
            to=[recipient],
            connection=connection,
        )
        message.attach_alternative(html, "text/html")
        if not message.send(fail_silently=False):
            raise RuntimeError("backend_returned_zero")
    except smtplib.SMTPAuthenticationError:
        return DeliveryResult("FAILED", "TENANT_SMTP", "smtp_authentication_failed")
    except (socket.timeout, TimeoutError):
        return DeliveryResult("FAILED", "TENANT_SMTP", "smtp_timeout")
    except ssl.SSLError:
        return DeliveryResult("FAILED", "TENANT_SMTP", "smtp_tls_failed")
    except ValidationError:
        return DeliveryResult("FAILED", "TENANT_SMTP", "smtp_destination_rejected")
    except (ConnectionError, OSError):
        return DeliveryResult("FAILED", "TENANT_SMTP", "smtp_connection_failed")
    except Exception as exc:
        return DeliveryResult("FAILED", "TENANT_SMTP", exc.__class__.__name__[:120])
    return DeliveryResult("SENT", "TENANT_SMTP")
