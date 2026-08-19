from django.conf import settings
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel


class Company(PublicIdModel, TimestampedModel):
    code = models.CharField(max_length=50, unique=True)
    legal_name = models.CharField(max_length=250)
    display_name = models.CharField(max_length=250)
    locale = models.CharField(max_length=35)
    timezone = models.CharField(max_length=64)
    currency = models.CharField(max_length=3)
    unit_system_code = models.CharField(max_length=50)
    fiscal_year_start_month = models.PositiveSmallIntegerField()
    branding_object_key = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    retention_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenant_company"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fiscal_year_start_month__gte=1)
                & models.Q(fiscal_year_start_month__lte=12),
                name="company_fiscal_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(closed_at__isnull=True)
                | models.Q(is_active=False),
                name="closed_company_not_active",
            ),
        ]


class Location(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="locations")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    location_type_code = models.CharField(max_length=100)
    address = models.JSONField(default=dict)
    timezone = models.CharField(max_length=64)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenant_location"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="location_company_code_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="location_effective_range_valid",
            ),
        ]


class Membership(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="company_memberships",
    )
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenant_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user"],
                name="membership_company_user_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="membership_effective_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "company", "suspended_at", "terminated_at"],
                name="membership_user_company_idx",
            )
        ]


class MembershipRole(PublicIdModel):
    membership = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role_public_id = models.UUIDField()
    assigned_by_public_id = models.UUIDField()
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tenant_membership_role"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role_public_id", "effective_from"],
                name="membership_role_effective_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="membership_role_range_valid",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not self.membership_id or not self.role_public_id:
            return
        from django.core.exceptions import ValidationError

        from modules.identity.models import Role

        valid_role = Role.objects.filter(
            public_id=self.role_public_id,
            company_public_id=self.membership.company.public_id,
        ).exists()
        if not valid_role:
            raise ValidationError("Role assignment cannot cross companies")



class CompanyBrandProfile(PublicIdModel, TimestampedModel):
    class SidebarStyle(models.TextChoices):
        LIGHT = "LIGHT", "Light"
        DARK = "DARK", "Dark"
        BRAND = "BRAND", "Brand"

    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="brand_profile",
    )
    product_name = models.CharField(max_length=120, blank=True)
    tagline = models.CharField(max_length=220, blank=True)
    logo_url = models.URLField(max_length=1000, blank=True)
    compact_logo_url = models.URLField(max_length=1000, blank=True)
    favicon_url = models.URLField(max_length=1000, blank=True)
    login_background_url = models.URLField(max_length=1000, blank=True)
    logo_file_public_id = models.UUIDField(null=True, blank=True)
    compact_logo_file_public_id = models.UUIDField(null=True, blank=True)
    favicon_file_public_id = models.UUIDField(null=True, blank=True)
    login_background_file_public_id = models.UUIDField(null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#174D3C")
    accent_color = models.CharField(max_length=7, default="#0F766E")
    sidebar_style = models.CharField(
        max_length=20,
        choices=SidebarStyle.choices,
        default=SidebarStyle.LIGHT,
    )
    sender_name = models.CharField(max_length=160, blank=True)
    support_email = models.EmailField(max_length=254, blank=True)
    document_footer = models.CharField(max_length=500, blank=True)
    powered_by_build360 = models.BooleanField(default=True)
    updated_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "tenant_company_brand_profile"

    def clean(self) -> None:
        super().clean()
        import re

        from django.core.exceptions import ValidationError

        color = re.compile(r"^#[0-9A-Fa-f]{6}$")
        if not color.fullmatch(self.primary_color):
            raise ValidationError({"primary_color": "Use a six-digit hex color such as #174D3C."})
        if not color.fullmatch(self.accent_color):
            raise ValidationError({"accent_color": "Use a six-digit hex color such as #0F766E."})



class CompanyEmailDeliveryProfile(PublicIdModel, TimestampedModel):
    class DeliveryMode(models.TextChoices):
        PLATFORM = "PLATFORM", "Build360 platform mail"
        TENANT_SMTP = "TENANT_SMTP", "Company SMTP"

    class Status(models.TextChoices):
        DISABLED = "DISABLED", "Disabled"
        PENDING = "PENDING", "Pending verification"
        ACTIVE = "ACTIVE", "Active"
        FAILED = "FAILED", "Verification failed"

    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="email_delivery_profile",
    )
    delivery_mode = models.CharField(
        max_length=20,
        choices=DeliveryMode.choices,
        default=DeliveryMode.PLATFORM,
    )
    smtp_host = models.CharField(max_length=253, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=320, blank=True)
    smtp_password_encrypted = models.TextField(blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField(max_length=254, blank=True)
    reply_to_email = models.EmailField(max_length=254, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DISABLED,
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=120, blank=True)
    updated_by_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "tenant_company_email_delivery_profile"

    def clean(self) -> None:
        super().clean()
        from django.core.exceptions import ValidationError

        host = (self.smtp_host or "").strip().lower().rstrip(".")
        self.smtp_host = host
        self.smtp_username = (self.smtp_username or "").strip()
        if host and ("://" in host or "/" in host or " " in host):
            raise ValidationError({"smtp_host": "Enter an SMTP hostname only, without scheme or path."})
        if not 1 <= int(self.smtp_port or 0) <= 65535:
            raise ValidationError({"smtp_port": "SMTP port must be between 1 and 65535."})
        if self.smtp_use_tls and self.smtp_use_ssl:
            raise ValidationError("SMTP TLS and SSL cannot both be enabled.")
        if self.delivery_mode == self.DeliveryMode.TENANT_SMTP:
            required = {}
            if not host:
                required["smtp_host"] = "SMTP host is required for company mail."
            if not self.from_email:
                required["from_email"] = "From email is required for company mail."
            if required:
                raise ValidationError(required)
        if self.status == self.Status.ACTIVE:
            if self.delivery_mode != self.DeliveryMode.TENANT_SMTP or self.verified_at is None:
                raise ValidationError("Only a verified company SMTP profile can be active.")


class TenantDomain(PublicIdModel, TimestampedModel):
    class DomainType(models.TextChoices):
        PLATFORM_SUBDOMAIN = "PLATFORM_SUBDOMAIN", "Build360 subdomain"
        CUSTOM_DOMAIN = "CUSTOM_DOMAIN", "Custom domain"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        FAILED = "FAILED", "Failed"
        SUSPENDED = "SUSPENDED", "Suspended"

    class SslStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        FAILED = "FAILED", "Failed"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="tenant_domains",
    )
    domain = models.CharField(max_length=253, unique=True)
    domain_type = models.CharField(max_length=30, choices=DomainType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_primary = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=96, blank=True)
    verification_record_name = models.CharField(max_length=300, blank=True)
    verification_record_value = models.CharField(max_length=500, blank=True)
    expected_cname = models.CharField(max_length=253, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_status = models.CharField(
        max_length=20,
        choices=SslStatus.choices,
        default=SslStatus.PENDING,
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "tenant_domain"
        ordering = ["-is_primary", "domain"]
        constraints = [
            models.UniqueConstraint(
                fields=["company"],
                condition=models.Q(is_primary=True),
                name="tenant_one_primary_domain_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["company", "status", "domain_type"],
                name="tenant_domain_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        import re

        from django.core.exceptions import ValidationError

        normalized = (self.domain or "").strip().lower().rstrip(".")
        if "://" in normalized or "/" in normalized or " " in normalized:
            raise ValidationError({"domain": "Enter a hostname only, without scheme or path."})
        if len(normalized) > 253:
            raise ValidationError({"domain": "Domain cannot exceed 253 characters."})
        label = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
        if not re.fullmatch(rf"{label}(?:\.{label})+", normalized):
            raise ValidationError({"domain": "Enter a valid DNS hostname."})
        self.domain = normalized
