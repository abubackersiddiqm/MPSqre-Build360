from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from modules.accessops.application.services import (
    STANDARD_COMPANY_ADMIN_ROLE_CODE,
    STANDARD_COMPANY_USER_ROLE_CODE,
)
from modules.accessops.models import CompanyAccessProfile, PlatformOperator
from modules.identity.application.permissions import effective_permission_codes
from modules.identity.models import Role, User
from modules.subscription.application.feature_control import (
    MODULE_CODES,
    _preset_values,
    feature_matrix,
)
from modules.tenant.models import Company, Membership

DEMO_MATRIX = {
    "DEMOCRM": {"package": "CRM_ONLY", "crm_ai": True},
    "DEMOCORE": {"package": "CONSTRUCTION_CORE", "crm_ai": False},
    "DEMO360": {"package": "FULL_BUILD360", "crm_ai": True},
}
ADMIN_EMAIL = "demo.admin@mpsqre.example"
USER_EMAIL = "demo.user@mpsqre.example"
SUPER_EMAIL = "demo.superadmin@mpsqre.example"


class Command(BaseCommand):
    help = "Validate the Build360 three-company demo package, role and identity isolation contract."

    def handle(self, *args: object, **options: object) -> None:
        if settings.BUILD360_ENVIRONMENT != "demo":
            raise CommandError("Demo access validation is blocked outside the DEMO environment.")
        db_name = str(settings.DATABASES["default"].get("NAME", ""))
        guard = os.getenv("BUILD360_DATABASE_NAME_GUARD", "").strip()
        if not guard or db_name != guard:
            raise CommandError("Demo database guard does not match the active database.")

        admin = self._user(ADMIN_EMAIL)
        user = self._user(USER_EMAIL)
        super_admin = self._user(SUPER_EMAIL)
        now = timezone.now()
        failures: list[str] = []

        if PlatformOperator.objects.filter(user=admin, is_active=True).exists():
            failures.append("Company Admin is incorrectly an active Platform Operator")
        if PlatformOperator.objects.filter(user=user, is_active=True).exists():
            failures.append("Company User is incorrectly an active Platform Operator")
        if not PlatformOperator.objects.filter(user=super_admin, is_active=True).exists():
            failures.append("Demo Super Admin is not an active Platform Operator")

        super_memberships = Membership.objects.filter(
            user=super_admin,
            company__code__in=DEMO_MATRIX.keys(),
            terminated_at__isnull=True,
            suspended_at__isnull=True,
            effective_from__lte=now,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        if super_memberships.exists():
            failures.append("Demo Super Admin unexpectedly has an active tenant membership")

        for company_code, spec in DEMO_MATRIX.items():
            company = Company.objects.filter(code=company_code, is_active=True).first()
            if company is None:
                failures.append(f"{company_code}: company missing")
                continue

            profile = CompanyAccessProfile.objects.filter(company=company).first()
            if profile is None or profile.plan_code != spec["package"]:
                failures.append(
                    f"{company_code}: plan_code expected {spec['package']} "
                    f"but found {getattr(profile, 'plan_code', None)}"
                )

            matrix = {
                str(item["code"]): bool(item["enabled"])
                for item in feature_matrix(company=company)["items"]
            }
            expected = _preset_values(str(spec["package"]))
            expected["crm.ai_summary"] = bool(spec["crm_ai"])
            expected["crm.ai_recommendation"] = bool(spec["crm_ai"])
            mismatches = [
                code
                for code, enabled in expected.items()
                if matrix.get(code, False) != enabled
            ]
            if mismatches:
                failures.append(
                    f"{company_code}: package entitlement mismatch: {', '.join(mismatches[:8])}"
                )

            if spec["package"] == "CRM_ONLY":
                # crm.core is intentionally a MODULE_CODE and is the core capability
                # that a CRM_ONLY package must enable. Validate unexpected modules
                # against the preset contract instead of incorrectly requiring every
                # MODULE_CODE to be disabled.
                enabled_modules = {
                    code for code in MODULE_CODES if matrix.get(code, False)
                }
                expected_modules = {
                    code for code in MODULE_CODES if expected.get(code, False)
                }
                unexpected_modules = sorted(enabled_modules - expected_modules)
                missing_modules = sorted(expected_modules - enabled_modules)
                if unexpected_modules:
                    failures.append(
                        f"{company_code}: CRM_ONLY unexpected modules: "
                        f"{', '.join(unexpected_modules)}"
                    )
                if missing_modules:
                    failures.append(
                        f"{company_code}: CRM_ONLY missing modules: "
                        f"{', '.join(missing_modules)}"
                    )

            admin_membership = self._active_membership(company=company, user=admin, now=now)
            user_membership = self._active_membership(company=company, user=user, now=now)
            if admin_membership is None:
                failures.append(f"{company_code}: Company Admin membership missing")
                continue
            if user_membership is None:
                failures.append(f"{company_code}: Company User membership missing")
                continue

            admin_role_codes, admin_permissions = self._roles_and_permissions(
                company=company,
                membership=admin_membership,
                now=now,
            )
            user_role_codes, user_permissions = self._roles_and_permissions(
                company=company,
                membership=user_membership,
                now=now,
            )

            if admin_role_codes != {
                STANDARD_COMPANY_ADMIN_ROLE_CODE,
                STANDARD_COMPANY_USER_ROLE_CODE,
            }:
                failures.append(
                    f"{company_code}: Admin active roles incorrect: {sorted(admin_role_codes)}"
                )
            if user_role_codes != {STANDARD_COMPANY_USER_ROLE_CODE}:
                failures.append(
                    f"{company_code}: User active roles incorrect: {sorted(user_role_codes)}"
                )

            if "access.user.manage" not in admin_permissions:
                failures.append(f"{company_code}: Admin lacks access.user.manage")
            if "access.user.manage" in user_permissions:
                failures.append(f"{company_code}: User incorrectly has access.user.manage")

            if spec["package"] == "CRM_ONLY":
                forbidden_prefixes = (
                    "project.",
                    "design.",
                    "estimation.",
                    "procurement.",
                    "vendor.",
                    "inventory.",
                    "field.",
                    "finance.",
                )
                leaked = sorted(
                    code
                    for code in user_permissions
                    if code.startswith(forbidden_prefixes)
                )
                if leaked:
                    failures.append(
                        f"{company_code}: CRM user has non-CRM permissions: {', '.join(leaked[:8])}"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {company_code} {spec['package']} | "
                    f"admin roles={sorted(admin_role_codes)} | "
                    f"user roles={sorted(user_role_codes)} | "
                    f"user permissions={len(user_permissions)}"
                )
            )

        if failures:
            for failure in failures:
                self.stdout.write(self.style.ERROR(f"[FAIL] {failure}"))
            raise CommandError(
                f"Build360 demo rights validation failed with {len(failures)} issue(s)."
            )

        self.stdout.write(self.style.SUCCESS("BUILD360 DEMO RIGHTS VALID"))
        self.stdout.write("DEMOCRM  : CRM_ONLY + CRM Sales Copilot (crm.core enabled by design)")
        self.stdout.write("DEMOCORE : CONSTRUCTION_CORE")
        self.stdout.write("DEMO360  : FULL_BUILD360 + CRM Sales Copilot")
        self.stdout.write("Admin    : COMPANY_ADMIN + package-derived COMPANY_USER")
        self.stdout.write("User     : package-derived COMPANY_USER only")
        self.stdout.write("Super    : Platform Operator only; no tenant membership")

    def _user(self, email: str) -> User:
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is None:
            raise CommandError(f"Required demo user is missing: {email}")
        return user

    def _active_membership(self, *, company: Company, user: User, now):
        return (
            Membership.objects.filter(
                company=company,
                user=user,
                effective_from__lte=now,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .first()
        )

    def _roles_and_permissions(self, *, company: Company, membership: Membership, now):
        role_ids = set(
            membership.role_assignments.filter(
                effective_from__lte=now,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
            .values_list("role_public_id", flat=True)
        )
        roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                public_id__in=role_ids,
            )
        )
        role_codes = {role.code for role in roles}
        permissions = effective_permission_codes(
            company_public_id=company.public_id,
            role_public_ids=role_ids,
        )
        return role_codes, permissions
