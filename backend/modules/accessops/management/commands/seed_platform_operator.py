from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.accessops.application.services import assign_membership_role
from modules.accessops.models import PlatformOperator
from modules.identity.models import Permission, Role, RolePermission, User
from modules.tenant.models import Membership

COMPANY_ACCESS_CODES = (
    "access.view",
    "access.manage",
    "access.user.manage",
    "access.invite",
    "access.role.manage",
    "access.membership.manage",
)


class Command(BaseCommand):
    help = "Create or activate a Build360 platform operator and grant company access administration."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="Build360 Platform Administrator")
        parser.add_argument("--password", default="")
        parser.add_argument("--operator-type", default="ROOT_OPERATOR")
        parser.add_argument(
            "--skip-company-access",
            action="store_true",
            help="Do not grant Access Administrator inside the user's existing companies.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            password = options["password"]
            if len(password) < 12:
                raise CommandError(
                    "A password of at least 12 characters is required when creating a new user."
                )
            user = User.objects.create_user(
                email=email,
                password=password,
                display_name=options["name"],
            )
            created_user = True
        else:
            created_user = False
            update_fields = ["is_active", "suspended_at", "updated_at"]
            if options["password"]:
                if len(options["password"]) < 12:
                    raise CommandError("Password must contain at least 12 characters.")
                user.set_password(options["password"])
                update_fields.append("password")
            user.is_active = True
            user.suspended_at = None
            user.save(update_fields=update_fields)

        operator, created_operator = PlatformOperator.objects.update_or_create(
            user=user,
            defaults={
                "operator_type_code": options["operator_type"].strip().upper(),
                "is_active": True,
            },
        )

        granted_companies = 0
        if not options["skip_company_access"]:
            now = timezone.now()
            permissions = list(Permission.objects.filter(code__in=COMPANY_ACCESS_CODES))
            memberships = Membership.objects.filter(
                user=user,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                company__is_active=True,
            ).select_related("company")
            for membership in memberships:
                role = Role.objects.filter(
                    company_public_id=membership.company.public_id,
                    code="ACCESS_ADMIN",
                    retired_at__isnull=True,
                ).order_by("-version").first()
                if role is None:
                    latest_version = (
                        Role.objects.filter(
                            company_public_id=membership.company.public_id,
                            code="ACCESS_ADMIN",
                        ).order_by("-version").values_list("version", flat=True).first()
                        or 0
                    )
                    role = Role.objects.create(
                        company_public_id=membership.company.public_id,
                        code="ACCESS_ADMIN",
                        name="Access Administrator",
                        version=latest_version + 1,
                        effective_from=now,
                    )
                for permission in permissions:
                    RolePermission.objects.get_or_create(role=role, permission=permission)
                if not membership.role_assignments.filter(
                    role_public_id=role.public_id,
                    effective_to__isnull=True,
                ).exists():
                    assign_membership_role(
                        membership=membership,
                        role=role,
                        assigned_by_public_id=user.public_id,
                        correlation_id=uuid.uuid4(),
                    )
                granted_companies += 1

        action = "created" if created_operator else "activated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Platform operator {action}: {user.email} ({operator.operator_type_code})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Company access administration granted in {granted_companies} active memberships."
            )
        )
        if created_user:
            self.stdout.write("A new identity user was also created.")
