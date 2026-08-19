from __future__ import annotations

import hashlib
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from modules.platform.models import PublicIdModel, TimestampedModel


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: object) -> User:
        if not email:
            raise ValueError("Email is required")
        normalized = self.normalize_email(email).strip().lower()
        user = self.model(email=normalized, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: object) -> User:
        return self._create_user(email, password, **extra)


class User(PublicIdModel, TimestampedModel, AbstractBaseUser):
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=200)
    preferred_locale = models.CharField(max_length=35, blank=True)
    is_active = models.BooleanField(default=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    last_security_event_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    class Meta:
        db_table = "identity_user"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="identity_user_email_ci_unique")
        ]


class AuthSession(PublicIdModel, TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="auth_sessions")
    device_id = models.UUIDField()
    device_name = models.CharField(max_length=200, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    assurance_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "identity_auth_session"
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="session_user_active_idx"),
            models.Index(fields=["expires_at"], name="session_expiry_idx"),
        ]


def hash_jti(jti: uuid.UUID) -> str:
    return hashlib.sha256(jti.bytes).hexdigest()


class RefreshToken(PublicIdModel):
    session = models.ForeignKey(AuthSession, on_delete=models.CASCADE, related_name="tokens")
    jti_hash = models.CharField(max_length=64, unique=True)
    family_id = models.UUIDField()
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by_jti_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "identity_refresh_token"
        indexes = [
            models.Index(fields=["session", "family_id"], name="refresh_family_idx"),
            models.Index(fields=["expires_at"], name="refresh_expiry_idx"),
        ]


class Permission(PublicIdModel, TimestampedModel):
    code = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=300)
    data_class = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "identity_permission"


class Role(PublicIdModel, TimestampedModel):
    company_public_id = models.UUIDField()
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identity_role"
        constraints = [
            models.UniqueConstraint(
                fields=["company_public_id", "code", "version"],
                name="role_company_code_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="role_effective_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company_public_id", "code", "effective_from"],
                name="role_company_effective_idx",
            )
        ]


class RolePermission(PublicIdModel):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="permission_grants")
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="role_grants",
    )

    class Meta:
        db_table = "identity_role_permission"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="role_permission_unique",
            )
        ]


class Invitation(PublicIdModel, TimestampedModel):
    company_public_id = models.UUIDField()
    email = models.EmailField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by_public_id = models.UUIDField()
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identity_invitation"
        indexes = [
            models.Index(
                fields=["company_public_id", "email", "expires_at"],
                name="invitation_company_email_idx",
            )
        ]
