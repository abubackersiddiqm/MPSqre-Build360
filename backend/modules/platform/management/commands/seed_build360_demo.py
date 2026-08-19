from __future__ import annotations

import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.accessops.application.services import (
    STANDARD_COMPANY_ADMIN_ROLE_CODE,
    assign_membership_role,
    create_role,
    set_company_feature_override,
    set_company_feature_preset,
    sync_company_user_role,
)
from modules.accessops.models import CompanyAccessProfile, PlatformOperator
from modules.crm.application.configuration import apply_industry_pack, ensure_foundation
from modules.crm.application.protection import (
    blind_index,
    encrypt_value,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from modules.crm.models import (
    Activity,
    Contact,
    Customer,
    Lead,
    Opportunity,
    PipelineStage,
    StageHistory,
)
from modules.identity.models import Permission, Role, User
from modules.projects.models import DeliveryStage, Project, ProjectTask, WbsNode
from modules.subscription.application.feature_control import (
    FEATURE_CATALOG,
    _preset_values,
    feature_matrix,
)
from modules.subscription.models import CompanySubscription, PlanVersion
from modules.tenant.models import Company, CompanyBrandProfile, Membership, MembershipRole

DEMO_EMAIL = "demo.admin@mpsqre.example"
DEMO_USER_EMAIL = "demo.user@mpsqre.example"
DEMO_SUPER_ADMIN_EMAIL = "demo.superadmin@mpsqre.example"
DEMO_USER_PASSWORD = "Build360User@2026"  # noqa: S105 -- synthetic DEMO-only credential
DEMO_SUPER_ADMIN_PASSWORD = "Build360SuperAdmin@2026"  # noqa: S105 -- synthetic DEMO-only credential

DEMO_COMPANIES = (
    {
        "code": "DEMOCRM",
        "display_name": "Build360 CRM Demo",
        "legal_name": "Build360 CRM Demo Private Limited",
        "package": "CRM_ONLY",
        "tagline": "CRM-only workspace",
        "seed_projects": False,
        "crm_ai": True,
    },
    {
        "code": "DEMOCORE",
        "display_name": "Build360 Construction Core Demo",
        "legal_name": "Build360 Construction Core Demo Private Limited",
        "package": "CONSTRUCTION_CORE",
        "tagline": "Core construction workspace",
        "seed_projects": True,
        "crm_ai": False,
    },
    {
        "code": "DEMO360",
        "display_name": "Build360 Full Suite Demo",
        "legal_name": "MPSqre Build360 Full Suite Demo Private Limited",
        "package": "FULL_BUILD360",
        "tagline": "Full Build360 workspace",
        "seed_projects": True,
        "crm_ai": True,
    },
)

COMPANY_ADMIN_PERMISSION_CODES = (
    "access.view",
    "access.user.manage",
    "tenant.branding.read",
    "tenant.branding.manage",
    "tenant.domain.read",
    "tenant.domain.manage",
)


class Command(BaseCommand):
    help = (
        "Seed three governed Build360 v1.0.0 demo tenants with correct "
        "package-derived Company User rights and isolated Company Admin/Super Admin access."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        # --company-code remains accepted for backward compatibility but R15 always
        # seeds the governed three-company demo matrix.
        parser.add_argument("--company-code", default="DEMO360")
        parser.add_argument("--admin-email", default=DEMO_EMAIL)
        parser.add_argument(
            "--admin-password",
            default=os.getenv("BUILD360_DEMO_ADMIN_PASSWORD", "Build360Demo@2026"),
        )
        parser.add_argument(
            "--user-email",
            default=os.getenv("BUILD360_DEMO_USER_EMAIL", DEMO_USER_EMAIL),
        )
        parser.add_argument(
            "--user-password",
            default=os.getenv("BUILD360_DEMO_USER_PASSWORD", DEMO_USER_PASSWORD),
        )
        parser.add_argument(
            "--super-admin-email",
            default=os.getenv("BUILD360_DEMO_SUPER_ADMIN_EMAIL", DEMO_SUPER_ADMIN_EMAIL),
        )
        parser.add_argument(
            "--super-admin-password",
            default=os.getenv(
                "BUILD360_DEMO_SUPER_ADMIN_PASSWORD",
                DEMO_SUPER_ADMIN_PASSWORD,
            ),
        )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        self._require_demo_database()

        admin_email = str(options["admin_email"]).strip().lower()
        admin_password = str(options["admin_password"])
        demo_user_email = str(options["user_email"]).strip().lower()
        demo_user_password = str(options["user_password"])
        super_admin_email = str(options["super_admin_email"]).strip().lower()
        super_admin_password = str(options["super_admin_password"])

        for label, password in (
            ("Demo administrator", admin_password),
            ("Demo user", demo_user_password),
            ("Demo Super Admin", super_admin_password),
        ):
            if len(password) < 12:
                raise CommandError(f"{label} password must contain at least 12 characters.")
        if len({admin_email, demo_user_email, super_admin_email}) != 3:
            raise CommandError("Demo administrator, user and Super Admin emails must be different.")

        now = timezone.now()
        admin_user = self._ensure_user(
            email=admin_email,
            password=admin_password,
            display_name="Demo Company Administrator",
        )
        demo_user = self._ensure_user(
            email=demo_user_email,
            password=demo_user_password,
            display_name="Demo Company User",
        )
        super_admin_user = self._ensure_user(
            email=super_admin_email,
            password=super_admin_password,
            display_name="Demo Super Administrator",
        )

        # Platform authorization must remain isolated from tenant identities.
        PlatformOperator.objects.filter(user__in=[admin_user, demo_user]).update(is_active=False)
        PlatformOperator.objects.update_or_create(
            user=super_admin_user,
            defaults={
                "operator_type_code": "ROOT_OPERATOR",
                "is_active": True,
                "created_by_public_id": super_admin_user.public_id,
            },
        )

        base_plan = self._ensure_demo_base_plan(now=now)
        seeded: list[tuple[Company, str]] = []

        for spec in DEMO_COMPANIES:
            company = self._ensure_company(spec=spec, now=now)
            self._ensure_subscription(
                company=company,
                base_plan=base_plan,
                now=now,
            )
            CompanyAccessProfile.objects.update_or_create(
                company=company,
                defaults={
                    "plan_code": spec["package"],
                    "onboarding_status_code": "ACTIVE",
                    "primary_admin_email": admin_email,
                    "created_by_public_id": super_admin_user.public_id,
                    "activated_at": now - timedelta(days=14),
                    "setup_completed_at": now - timedelta(days=13),
                },
            )

            self._ensure_package(
                company=company,
                preset_code=str(spec["package"]),
                crm_ai=bool(spec["crm_ai"]),
                actor_public_id=super_admin_user.public_id,
            )

            profile = ensure_foundation(company)
            if profile.industry_code != "construction":
                apply_industry_pack(company=company, pack_code="construction")

            if bool(spec["crm_ai"]):
                call_command(
                    "bootstrap_crm_ai_lead_intelligence",
                    company_code=company.code,
                    verbosity=0,
                )

            admin_membership = self._ensure_membership(
                company=company,
                user=admin_user,
                now=now,
            )
            user_membership = self._ensure_membership(
                company=company,
                user=demo_user,
                now=now,
            )

            company_user_role = sync_company_user_role(
                company=company,
                actor_public_id=super_admin_user.public_id,
                correlation_id=uuid.uuid4(),
            )
            company_admin_role = self._ensure_company_admin_role(
                company=company,
                actor_public_id=super_admin_user.public_id,
            )

            # Remove the over-broad R14 demo roles and enforce the real SaaS role model.
            self._retire_legacy_demo_roles(company=company, now=now)
            self._set_exact_roles(
                membership=admin_membership,
                roles=(company_admin_role, company_user_role),
                actor_public_id=super_admin_user.public_id,
                now=now,
            )
            self._set_exact_roles(
                membership=user_membership,
                roles=(company_user_role,),
                actor_public_id=super_admin_user.public_id,
                now=now,
            )

            # Demo business records belong to the normal employee/user so the user
            # workspace is realistic. Company Admin can still see them through the
            # same purchased business permissions plus tenant administration rights.
            self._seed_crm(
                company=company,
                membership=user_membership,
                user=demo_user,
                now=now,
            )
            if bool(spec["seed_projects"]):
                self._seed_projects(
                    company=company,
                    membership=user_membership,
                    user=demo_user,
                    now=now,
                )

            seeded.append((company, str(spec["package"])))

        # Super Admin should never acquire a tenant membership from demo data.
        Membership.objects.filter(
            company__code__in=[spec["code"] for spec in DEMO_COMPANIES],
            user=super_admin_user,
        ).update(terminated_at=now)

        database_name = str(settings.DATABASES["default"].get("NAME", ""))
        self.stdout.write(self.style.SUCCESS("BUILD360 THREE-COMPANY DEMO DATA READY"))
        self.stdout.write("Environment : DEMO")
        self.stdout.write(f"Version     : v{settings.APP_VERSION}")
        self.stdout.write(f"Database    : {database_name}")
        self.stdout.write("Companies   :")
        for company, package_code in seeded:
            ai_note = " + CRM AI" if package_code in {"CRM_ONLY", "FULL_BUILD360"} else ""
            self.stdout.write(
                f"  - {company.display_name} ({company.code}) -> {package_code}{ai_note}"
            )
        self.stdout.write("Tenant URL  : http://localhost:3000/sign-in")
        self.stdout.write(f"Admin login : {admin_email} / {admin_password}")
        self.stdout.write(f"User login  : {demo_user_email} / {demo_user_password}")
        self.stdout.write("  Both tenant logins belong to all 3 demo companies.")
        self.stdout.write("  Admin roles: COMPANY_ADMIN + package-derived COMPANY_USER.")
        self.stdout.write("  User role : package-derived COMPANY_USER only.")
        self.stdout.write("Super Admin : http://localhost:3000/super-admin/sign-in")
        self.stdout.write(f"Super login : {super_admin_email} / {super_admin_password}")
        self.stdout.write("AI provider : LOCAL_GROUNDED / local_grounded")
        self.stdout.write("AI model    : build360-local-grounded-crm-v2")
        self.stdout.write("AI enabled  : DEMOCRM and DEMO360")
        self.stdout.write(
            self.style.WARNING(
                "Demo credentials and data are fake and must never be copied into production."
            )
        )

    def _require_demo_database(self) -> None:
        if settings.BUILD360_ENVIRONMENT != "demo":
            raise CommandError(
                "Demo seeding is blocked outside BUILD360_ENVIRONMENT=demo."
            )
        database_name = str(settings.DATABASES["default"].get("NAME", ""))
        guard = os.getenv("BUILD360_DATABASE_NAME_GUARD", "").strip()
        if not guard or database_name != guard:
            raise CommandError(
                "Demo database name guard is missing or does not match DATABASE_URL."
            )

    def _ensure_user(self, *, email: str, password: str, display_name: str) -> User:
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            return User.objects.create_user(
                email=email,
                password=password,
                display_name=display_name,
                preferred_locale="en-IN",
            )
        user.display_name = display_name
        user.is_active = True
        user.suspended_at = None
        user.terminated_at = None
        user.set_password(password)
        user.save()
        return user

    def _ensure_demo_base_plan(self, *, now) -> PlanVersion:
        plan = PlanVersion.objects.filter(code="BUILD360_DEMO_BASE", version=1).first()
        if plan is not None:
            return plan
        return PlanVersion.objects.create(
            code="BUILD360_DEMO_BASE",
            version=1,
            name="Build360 Demo Base",
            status=PlanVersion.Status.PUBLISHED,
            entitlements={feature.code: False for feature in FEATURE_CATALOG},
            limits={"users": 500, "projects": 1000, "crm.contacts": 100000},
            effective_from=now - timedelta(days=365),
            published_at=now - timedelta(days=365),
        )

    def _ensure_company(self, *, spec: dict[str, object], now) -> Company:
        code = str(spec["code"])
        company, _ = Company.objects.update_or_create(
            code=code,
            defaults={
                "legal_name": str(spec["legal_name"]),
                "display_name": str(spec["display_name"]),
                "locale": "en-IN",
                "timezone": "Asia/Kolkata",
                "currency": "INR",
                "unit_system_code": "metric",
                "fiscal_year_start_month": 4,
                "is_active": True,
                "suspended_at": None,
                "closed_at": None,
            },
        )
        brand_colors = {
            "DEMOCRM": ("#4F46E5", "#7C3AED"),
            "DEMOCORE": ("#B45309", "#D97706"),
            "DEMO360": ("#174D3C", "#0F766E"),
        }
        primary, accent = brand_colors[code]
        CompanyBrandProfile.objects.update_or_create(
            company=company,
            defaults={
                "product_name": "MPSqre Build360",
                "tagline": str(spec["tagline"]),
                "primary_color": primary,
                "accent_color": accent,
                "sidebar_style": CompanyBrandProfile.SidebarStyle.LIGHT,
                "sender_name": str(spec["display_name"]),
                "support_email": f"{code.lower()}-support@mpsqre.example",
                "powered_by_build360": True,
            },
        )
        return company

    def _ensure_subscription(
        self,
        *,
        company: Company,
        base_plan: PlanVersion,
        now,
    ) -> None:
        # End any older demo subscription so effective_entitlements() has one
        # deterministic active base plan before package overrides are evaluated.
        CompanySubscription.objects.filter(company=company).exclude(
            plan_version=base_plan
        ).filter(
            status__in=[
                CompanySubscription.Status.TRIAL,
                CompanySubscription.Status.ACTIVE,
                CompanySubscription.Status.GRACE,
            ]
        ).update(
            status=CompanySubscription.Status.ENDED,
            ends_at=now,
            grace_until=None,
        )
        subscription = CompanySubscription.objects.filter(
            company=company,
            plan_version=base_plan,
        ).order_by("-starts_at").first()
        if subscription is None:
            CompanySubscription.objects.create(
                company=company,
                plan_version=base_plan,
                status=CompanySubscription.Status.ACTIVE,
                starts_at=now - timedelta(days=30),
                ends_at=now + timedelta(days=3650),
                grace_until=None,
            )
        else:
            subscription.status = CompanySubscription.Status.ACTIVE
            subscription.starts_at = now - timedelta(days=30)
            subscription.ends_at = now + timedelta(days=3650)
            subscription.grace_until = None
            subscription.save()

    def _ensure_package(
        self,
        *,
        company: Company,
        preset_code: str,
        crm_ai: bool,
        actor_public_id: uuid.UUID,
    ) -> None:
        desired = _preset_values(preset_code)
        desired["crm.ai_summary"] = crm_ai
        desired["crm.ai_recommendation"] = crm_ai

        current = {
            str(item["code"]): bool(item["enabled"])
            for item in feature_matrix(company=company)["items"]
        }
        preset_desired = _preset_values(preset_code)
        if any(current.get(code, False) != enabled for code, enabled in preset_desired.items()):
            set_company_feature_preset(
                company=company,
                preset_code=preset_code,
                reason_code="demo-package",
                actor_public_id=actor_public_id,
                correlation_id=uuid.uuid4(),
            )
            current = {
                str(item["code"]): bool(item["enabled"])
                for item in feature_matrix(company=company)["items"]
            }

        for feature_code in ("crm.ai_summary", "crm.ai_recommendation"):
            enabled = bool(desired[feature_code])
            if current.get(feature_code, False) != enabled:
                set_company_feature_override(
                    company=company,
                    feature_code=feature_code,
                    enabled=enabled,
                    reason_code="demo-crm-ai",
                    actor_public_id=actor_public_id,
                    correlation_id=uuid.uuid4(),
                )

    def _ensure_membership(self, *, company: Company, user: User, now) -> Membership:
        membership, _ = Membership.objects.update_or_create(
            company=company,
            user=user,
            defaults={
                "effective_from": now - timedelta(days=30),
                "effective_to": None,
                "suspended_at": None,
                "terminated_at": None,
            },
        )
        return membership

    def _ensure_company_admin_role(
        self,
        *,
        company: Company,
        actor_public_id: uuid.UUID,
    ) -> Role:
        missing = [
            code
            for code in COMPANY_ADMIN_PERMISSION_CODES
            if not Permission.objects.filter(code=code).exists()
        ]
        if missing:
            raise CommandError(
                "Required Company Admin permissions are missing: " + ", ".join(missing)
            )
        current = (
            Role.objects.filter(
                company_public_id=company.public_id,
                code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
                retired_at__isnull=True,
            )
            .order_by("-version")
            .first()
        )
        desired = set(COMPANY_ADMIN_PERMISSION_CODES)
        if current is not None:
            current_codes = set(
                current.permission_grants.values_list("permission__code", flat=True)
            )
            if current_codes == desired:
                return current
        return create_role(
            company=company,
            code=STANDARD_COMPANY_ADMIN_ROLE_CODE,
            name="Company Administrator",
            permission_codes=list(COMPANY_ADMIN_PERMISSION_CODES),
            actor_public_id=actor_public_id,
            correlation_id=uuid.uuid4(),
        )

    def _retire_legacy_demo_roles(self, *, company: Company, now) -> None:
        legacy_roles = list(
            Role.objects.filter(
                company_public_id=company.public_id,
                code__in=["DEMO_ADMIN", "DEMO_USER"],
                retired_at__isnull=True,
            )
        )
        if not legacy_roles:
            return
        legacy_ids = [role.public_id for role in legacy_roles]
        MembershipRole.objects.filter(
            membership__company=company,
            role_public_id__in=legacy_ids,
            effective_to__isnull=True,
        ).update(effective_to=now)
        Role.objects.filter(public_id__in=legacy_ids).update(
            retired_at=now,
            effective_to=now,
        )

    def _set_exact_roles(
        self,
        *,
        membership: Membership,
        roles: tuple[Role, ...],
        actor_public_id: uuid.UUID,
        now,
    ) -> None:
        desired_ids = {role.public_id for role in roles}
        active = list(
            membership.role_assignments.filter(
                effective_from__lte=now,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gt=now)
            )
        )
        for assignment in active:
            if assignment.role_public_id not in desired_ids:
                assignment.effective_to = now
                assignment.save(update_fields=["effective_to"])

        current_ids = {
            assignment.role_public_id
            for assignment in membership.role_assignments.filter(
                effective_from__lte=now,
                effective_to__isnull=True,
            )
        }
        for role in roles:
            if role.public_id in current_ids:
                continue
            assign_membership_role(
                membership=membership,
                role=role,
                assigned_by_public_id=actor_public_id,
                correlation_id=uuid.uuid4(),
            )

    def _seed_crm(self, *, company: Company, membership: Membership, user: User, now) -> None:
        lead_stages = {
            stage.code: stage
            for stage in PipelineStage.objects.filter(company=company, entity_type="lead", is_active=True)
        }
        opportunity_stages = {
            stage.code: stage
            for stage in PipelineStage.objects.filter(company=company, entity_type="opportunity", is_active=True)
        }

        customer_defs = [
            ("CUST-ZENITH", "Zenith Developers Pvt Ltd", "organization"),
            ("CUST-GREENNEST", "GreenNest Homes", "organization"),
            ("CUST-METRO", "Metro Retail Fitouts", "organization"),
            ("CUST-ARCADIA", "Arcadia Industries", "organization"),
            ("CUST-RIVER", "Riverstone Estates", "organization"),
            ("CUST-PRIYA", "Priya Residence", "person"),
        ]
        customers: dict[str, Customer] = {}
        for ref, name, kind in customer_defs:
            customer, _ = Customer.objects.update_or_create(
                company=company,
                external_reference=ref,
                defaults={
                    "kind": kind,
                    "display_name": name,
                    "legal_name": name if kind == "organization" else "",
                    "normalized_name": normalize_name(name),
                    "source_code": "demo",
                    "status": Customer.Status.ACTIVE,
                    "owner_membership_public_id": membership.public_id,
                    "notes": "Synthetic record created for the Build360 demo database.",
                },
            )
            customers[ref] = customer

        contacts_data = [
            ("ZENITH", "Arun", "Kumar", "Project Director", "arun.zenith@example.com", "+919000000101", "+919000000201", "CUST-ZENITH"),
            ("GREEN", "Meena", "Ravi", "Founder", "meena.greennest@example.com", "+919000000102", "", "CUST-GREENNEST"),
            ("METRO", "Karthik", "S", "Expansion Manager", "karthik.metro@example.com", "+919000000103", "+919000000203", "CUST-METRO"),
            ("ARCADIA", "Naveen", "Raj", "Plant Head", "naveen.arcadia@example.com", "+919000000104", "", "CUST-ARCADIA"),
            ("RIVER", "Divya", "M", "Sales Director", "divya.river@example.com", "+919000000105", "", "CUST-RIVER"),
            ("PRIYA", "Priya", "S", "Home Owner", "priya.home@example.com", "+919000000106", "+919000000206", "CUST-PRIYA"),
            ("ZENITH2", "Vikram", "R", "Procurement Lead", "vikram.zenith@example.com", "+919000000107", "", "CUST-ZENITH"),
            ("GREEN2", "Sanjay", "K", "Architect", "sanjay.greennest@example.com", "+919000000108", "", "CUST-GREENNEST"),
            ("METRO2", "Lakshmi", "P", "Finance Manager", "lakshmi.metro@example.com", "+919000000109", "", "CUST-METRO"),
            ("LEELA", "Leela", "N", "Independent Architect", "leela.arch@example.com", "+919000000110", "", None),
        ]
        contacts: dict[str, Contact] = {}
        for key, first, last, title, email, phone, alt_phone, customer_ref in contacts_data:
            normalized_email = normalize_email(email)
            normalized_phone = normalize_phone(phone)
            normalized_alt = normalize_phone(alt_phone)
            phone_index = blind_index(normalized_phone, purpose="phone")
            contact = Contact.objects.filter(company=company, phone_blind_index=phone_index).first()
            values = {
                "customer": customers.get(customer_ref) if customer_ref else None,
                "first_name": first,
                "last_name": last,
                "job_title": title,
                "email_ciphertext": encrypt_value(normalized_email),
                "email_blind_index": blind_index(normalized_email, purpose="email"),
                "phone_ciphertext": encrypt_value(normalized_phone),
                "phone_blind_index": phone_index,
                "alternate_phone_ciphertext": encrypt_value(normalized_alt),
                "alternate_phone_blind_index": blind_index(normalized_alt, purpose="phone"),
                "email_last_four": normalized_email[-4:],
                "phone_last_four": normalized_phone[-4:],
                "alternate_phone_last_four": normalized_alt[-4:] if normalized_alt else "",
                "consent_status": Contact.ConsentStatus.GRANTED,
                "preferred_channel_code": "whatsapp",
                "source_code": "demo",
                "tags": ["demo", "construction"],
                "notes": "Synthetic demo contact.",
                "owner_membership_public_id": membership.public_id,
                "is_active": True,
            }
            if contact is None:
                contact = Contact.objects.create(company=company, **values)
            else:
                for field, value in values.items():
                    setattr(contact, field, value)
                contact.save()
            contacts[key] = contact

        lead_defs = [
            ("ZENITH", "Zenith premium residences - design and build", "qualified", "website", Decimal("85000000"), now - timedelta(days=2), "Commercial", "Chennai", 78000, "Ready to start"),
            ("GREEN", "GreenNest villa community phase 2", "contacted", "referral", Decimal("46000000"), now + timedelta(hours=2), "Residential", "Coimbatore", 52000, "Design"),
            ("METRO", "Metro flagship retail interior", "new", "event", Decimal("12500000"), now + timedelta(days=1), "Commercial", "Bengaluru", 18000, "Planning"),
            ("ARCADIA", "Arcadia plant expansion civil package", "qualified", "phone", Decimal("72000000"), now + timedelta(days=3), "Industrial", "Hosur", 110000, "Approval"),
            ("RIVER", "Riverstone apartment clubhouse", "contacted", "meta_ads", Decimal("18000000"), None, "Residential", "Chennai", 24000, "Planning"),
            ("PRIYA", "Priya residence turnkey construction", "new", "whatsapp", Decimal("9500000"), now - timedelta(hours=4), "Residential", "Chennai", 3400, "Ready to start"),
            ("ZENITH2", "Zenith procurement advisory requirement", "new", "email", Decimal("2500000"), now + timedelta(days=5), "Commercial", "Chennai", 0, "Ongoing"),
            ("GREEN2", "GreenNest landscape and amenities", "contacted", "partner", Decimal("6500000"), now + timedelta(hours=26), "Residential", "Coimbatore", 15000, "Design"),
            ("METRO2", "Metro cost optimisation review", "qualified", "email", Decimal("3200000"), None, "Commercial", "Bengaluru", 18000, "Ongoing"),
            ("LEELA", "Architect collaboration - upcoming villa", "new", "referral", Decimal("14000000"), now + timedelta(days=2), "Residential", "Erode", 6200, "Planning"),
        ]
        leads: dict[str, Lead] = {}
        for key, title, stage_code, source, value, follow_up, project_type, location, area, construction_stage in lead_defs:
            contact = contacts[key]
            stage = lead_stages[stage_code]
            custom_fields = {
                "project_type": project_type,
                "site_location": location,
                "built_up_area": area,
                "budget": float(value),
                "construction_stage": construction_stage,
            }
            lead = Lead.objects.filter(company=company, title=title, primary_contact=contact).first()
            created = lead is None
            if created:
                lead = Lead.objects.create(
                    company=company,
                    title=title,
                    description="Synthetic sales enquiry for Build360 demo walkthrough.",
                    source_code=source,
                    stage=stage,
                    customer=contact.customer,
                    primary_contact=contact,
                    owner_membership_public_id=membership.public_id,
                    estimated_value=value,
                    currency="INR",
                    next_follow_up_at=follow_up,
                    custom_fields=custom_fields,
                )
            else:
                lead.stage = stage
                lead.source_code = source
                lead.estimated_value = value
                lead.next_follow_up_at = follow_up
                lead.custom_fields = custom_fields
                lead.save()
            if created:
                StageHistory.objects.create(
                    company=company,
                    entity_type="lead",
                    entity_public_id=lead.public_id,
                    from_stage_code="",
                    to_stage_code=stage.code,
                    changed_by_public_id=user.public_id,
                    changed_at=now - timedelta(days=10),
                    entity_version=lead.version,
                )
            leads[key] = lead

        opportunity_defs = [
            ("ZENITH", "Zenith Residences Main Contract", "proposal", Decimal("85000000"), 28),
            ("GREEN", "GreenNest Villas Phase 2", "negotiation", Decimal("46000000"), 18),
            ("ARCADIA", "Arcadia Expansion Package", "qualification", Decimal("72000000"), 45),
            ("PRIYA", "Priya Turnkey Home", "proposal", Decimal("9500000"), 12),
        ]
        opportunities: dict[str, Opportunity] = {}
        for key, name, stage_code, amount, close_days in opportunity_defs:
            lead = leads[key]
            stage = opportunity_stages[stage_code]
            opportunity = Opportunity.objects.filter(company=company, source_lead=lead).first()
            if opportunity is None:
                opportunity = Opportunity.objects.create(
                    company=company,
                    name=name,
                    customer=lead.customer,
                    primary_contact=lead.primary_contact,
                    source_lead=lead,
                    stage=stage,
                    owner_membership_public_id=membership.public_id,
                    amount=amount,
                    currency="INR",
                    expected_close_date=(now + timedelta(days=close_days)).date(),
                    probability_percent=stage.probability_percent,
                )
                StageHistory.objects.create(
                    company=company,
                    entity_type="opportunity",
                    entity_public_id=opportunity.public_id,
                    from_stage_code="",
                    to_stage_code=stage.code,
                    changed_by_public_id=user.public_id,
                    changed_at=now - timedelta(days=7),
                    entity_version=opportunity.version,
                )
            opportunities[key] = opportunity

        activity_defs = [
            ("ZENITH", Activity.ActivityType.CALL, "Budget and timeline discovery call", "Decision team wants a revised milestone plan.", -5, Activity.Status.COMPLETED, "connected", 540),
            ("ZENITH", Activity.ActivityType.EMAIL, "Revised proposal shared", "Proposal v2 shared for commercial review.", -3, Activity.Status.COMPLETED, "sent", None),
            ("GREEN", Activity.ActivityType.WHATSAPP, "Shared concept plan", "Customer confirmed design preference and asked for cost options.", -2, Activity.Status.COMPLETED, "replied", None),
            ("GREEN", Activity.ActivityType.CALL, "Negotiation follow-up", "Call customer before commercial committee meeting.", 0, Activity.Status.PLANNED, "", None),
            ("PRIYA", Activity.ActivityType.CALL, "Callback requested", "Customer asked for a callback about revised scope.", -1, Activity.Status.PLANNED, "callback_requested", None),
            ("METRO", Activity.ActivityType.MEETING, "Requirement discovery meeting", "Walk through retail fit-out scope and opening deadline.", 1, Activity.Status.PLANNED, "", None),
            ("ARCADIA", Activity.ActivityType.EMAIL, "Technical capability note", "Shared industrial execution capability summary.", -1, Activity.Status.COMPLETED, "sent", None),
            ("LEELA", Activity.ActivityType.FOLLOW_UP, "Architect collaboration follow-up", "Discuss joint delivery model and referral terms.", 2, Activity.Status.PLANNED, "", None),
        ]
        for key, activity_type, subject, notes, day_offset, status, outcome, duration in activity_defs:
            contact = contacts[key]
            lead = leads[key]
            scheduled = now + timedelta(days=day_offset)
            exists = Activity.objects.filter(company=company, contact=contact, subject=subject).exists()
            if exists:
                continue
            Activity.objects.create(
                company=company,
                customer=contact.customer,
                contact=contact,
                lead=lead,
                opportunity=opportunities.get(key),
                activity_type=activity_type,
                status=status,
                direction=Activity.Direction.OUTBOUND,
                outcome_code=outcome,
                duration_seconds=duration,
                subject=subject,
                notes=notes,
                scheduled_for=scheduled,
                follow_up_at=(scheduled + timedelta(days=1)) if status == Activity.Status.COMPLETED else scheduled,
                occurred_at=scheduled if status == Activity.Status.COMPLETED else None,
                completed_at=scheduled if status == Activity.Status.COMPLETED else None,
                priority=Activity.Priority.HIGH if key in {"ZENITH", "PRIYA"} else Activity.Priority.NORMAL,
                owner_membership_public_id=membership.public_id,
                created_by_public_id=user.public_id,
            )

    def _seed_projects(self, *, company: Company, membership: Membership, user: User, now) -> None:
        project_stage_defs = [
            ("preconstruction", "Preconstruction", "open", 10, True, ["execution"]),
            ("execution", "Execution", "open", 20, False, ["handover"]),
            ("handover", "Handover", "review", 30, False, ["complete"]),
            ("complete", "Complete", "complete", 90, False, []),
        ]
        task_stage_defs = [
            ("planned", "Planned", "open", 10, True, ["in_progress"]),
            ("in_progress", "In progress", "open", 20, False, ["complete"]),
            ("complete", "Complete", "complete", 90, False, []),
        ]
        project_stages: dict[str, DeliveryStage] = {}
        task_stages: dict[str, DeliveryStage] = {}
        for code, name, outcome, order, initial, next_codes in project_stage_defs:
            stage, _ = DeliveryStage.objects.update_or_create(
                company=company,
                entity_type=DeliveryStage.EntityType.PROJECT,
                code=code,
                defaults={
                    "name": name,
                    "outcome": outcome,
                    "sort_order": order,
                    "allowed_next_codes": next_codes,
                    "is_initial": initial,
                    "is_active": True,
                    "effective_from": now - timedelta(days=30),
                    "effective_to": None,
                },
            )
            project_stages[code] = stage
        for code, name, outcome, order, initial, next_codes in task_stage_defs:
            stage, _ = DeliveryStage.objects.update_or_create(
                company=company,
                entity_type=DeliveryStage.EntityType.TASK,
                code=code,
                defaults={
                    "name": name,
                    "outcome": outcome,
                    "sort_order": order,
                    "allowed_next_codes": next_codes,
                    "is_initial": initial,
                    "is_active": True,
                    "effective_from": now - timedelta(days=30),
                    "effective_to": None,
                },
            )
            task_stages[code] = stage

        project_defs = [
            ("DEMO-ZEN-01", "Zenith Residences", "execution", Decimal("85000000"), -30, 270, "Chennai"),
            ("DEMO-GRN-02", "GreenNest Villas Phase 2", "preconstruction", Decimal("46000000"), 14, 320, "Coimbatore"),
            ("DEMO-ARC-03", "Arcadia Plant Expansion", "execution", Decimal("72000000"), -60, 220, "Hosur"),
        ]
        for code, name, stage_code, budget, start_offset, end_offset, city in project_defs:
            project, _ = Project.objects.update_or_create(
                company=company,
                code=code,
                defaults={
                    "name": name,
                    "description": "Synthetic Build360 demonstration project.",
                    "stage": project_stages[stage_code],
                    "manager_membership_public_id": membership.public_id,
                    "location": {"city": city, "state": "Tamil Nadu" if city != "Bengaluru" else "Karnataka"},
                    "planned_start_date": (now + timedelta(days=start_offset)).date(),
                    "planned_end_date": (now + timedelta(days=end_offset)).date(),
                    "currency": "INR",
                    "approved_budget": budget,
                },
            )
            wbs, _ = WbsNode.objects.update_or_create(
                company=company,
                project=project,
                code="01",
                defaults={"name": "Main delivery", "sort_order": 10},
            )
            tasks = [
                ("T001", "Design coordination", "complete", 100),
                ("T002", "Procurement package release", "in_progress", 55),
                ("T003", "Site execution milestone", "planned", 10),
            ]
            for task_code, title, task_stage_code, progress in tasks:
                ProjectTask.objects.update_or_create(
                    company=company,
                    project=project,
                    code=task_code,
                    defaults={
                        "wbs_node": wbs,
                        "title": title,
                        "stage": task_stages[task_stage_code],
                        "assignee_membership_public_id": membership.public_id,
                        "planned_start_date": (now - timedelta(days=10)).date(),
                        "planned_end_date": (now + timedelta(days=30)).date(),
                        "progress_percent": progress,
                    },
                )
