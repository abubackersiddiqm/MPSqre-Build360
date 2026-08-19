from __future__ import annotations

import getpass
import os
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from modules.accessops.models import PlatformOperator
from modules.identity.models import User


ALLOWED_ENVIRONMENTS = {
    "testing": "build360_testing",
    "production": "build360_production",
}


class Command(BaseCommand):
    help = (
        "One-time bootstrap of the first Build360 ROOT_OPERATOR. "
        "This is not a demo/test seed and never creates a tenant/company."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--email",
            help="ROOT_OPERATOR email. If omitted, prompts interactively.",
        )
        parser.add_argument(
            "--display-name",
            help="Display name. If omitted, prompts interactively.",
        )
        parser.add_argument(
            "--verify-only",
            action="store_true",
            help="Verify an active ROOT_OPERATOR exists without mutating data.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        environment = str(
            getattr(settings, "BUILD360_ENVIRONMENT", "") or ""
        ).strip().lower()
        database_name = str(
            settings.DATABASES["default"].get("NAME", "") or ""
        ).strip()
        database_guard = os.getenv(
            "BUILD360_DATABASE_NAME_GUARD",
            "",
        ).strip()

        expected_database = ALLOWED_ENVIRONMENTS.get(environment)
        if expected_database is None:
            raise CommandError(
                "ROOT_OPERATOR bootstrap is allowed only in TESTING or PRODUCTION. "
                f"Current environment: {environment or 'UNKNOWN'}."
            )

        if database_name != expected_database:
            raise CommandError(
                "Database safety guard failed. "
                f"Environment {environment.upper()} requires DB "
                f"'{expected_database}', got '{database_name}'."
            )

        if database_guard != expected_database:
            raise CommandError(
                "BUILD360_DATABASE_NAME_GUARD safety check failed. "
                f"Expected exactly '{expected_database}'."
            )

        roots = list(
            PlatformOperator.objects.select_related("user")
            .filter(
                operator_type_code="ROOT_OPERATOR",
                is_active=True,
                user__is_active=True,
            )
            .order_by("created_at")
        )

        if options["verify_only"]:
            if not roots:
                raise CommandError("No active ROOT_OPERATOR exists.")
            if len(roots) > 1:
                raise CommandError(
                    f"Security invariant failed: {len(roots)} active ROOT_OPERATOR "
                    "records exist. Review before continuing."
                )
            root = roots[0]
            self.stdout.write(
                self.style.SUCCESS(
                    "ROOT_OPERATOR verified: "
                    f"{root.user.email} / {environment.upper()} / {database_name}"
                )
            )
            return

        if roots:
            root = roots[0]
            if len(roots) > 1:
                raise CommandError(
                    f"Security invariant failed: {len(roots)} active ROOT_OPERATOR "
                    "records already exist. Bootstrap refused."
                )
            self.stdout.write(
                self.style.SUCCESS(
                    "ROOT_OPERATOR already exists; bootstrap is idempotent."
                )
            )
            self.stdout.write(f"Email       : {root.user.email}")
            self.stdout.write(f"Environment : {environment.upper()}")
            self.stdout.write(f"Database    : {database_name}")
            return

        email = str(options.get("email") or "").strip().lower()
        if not email:
            email = input("ROOT_OPERATOR email: ").strip().lower()
        if "@" not in email:
            raise CommandError("Enter a valid email address.")

        display_name = str(options.get("display_name") or "").strip()
        if not display_name:
            display_name = (
                input("Display name [Build360 Root Operator]: ").strip()
                or "Build360 Root Operator"
            )

        password = getpass.getpass("Password (minimum 14 characters): ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            raise CommandError("Passwords do not match.")
        if len(password) < 14:
            raise CommandError("Password must contain at least 14 characters.")
        email_local_part = email.split("@", 1)[0].lower()
        if email_local_part and email_local_part in password.lower():
            raise CommandError(
                "Password must not contain the email username."
            )

        with transaction.atomic():
            user = (
                User.objects.select_for_update()
                .filter(email__iexact=email)
                .first()
            )

            if user is None:
                user = User(
                    email=email,
                    display_name=display_name,
                )
            else:
                existing_operator = (
                    PlatformOperator.objects.select_for_update()
                    .filter(user=user)
                    .first()
                )
                if (
                    existing_operator is not None
                    and existing_operator.operator_type_code != "ROOT_OPERATOR"
                    and existing_operator.is_active
                ):
                    raise CommandError(
                        "This email already belongs to another active platform "
                        "operator type. Bootstrap refused."
                    )

            user.email = email
            user.display_name = display_name
            user.is_active = True
            user.suspended_at = None
            user.terminated_at = None
            user.set_password(password)
            user.full_clean()
            user.save()

            PlatformOperator.objects.update_or_create(
                user=user,
                defaults={
                    "operator_type_code": "ROOT_OPERATOR",
                    "is_active": True,
                    "created_by_public_id": user.public_id,
                },
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("ROOT_OPERATOR BOOTSTRAP SUCCESS"))
        self.stdout.write(f"Email       : {email}")
        self.stdout.write(f"Environment : {environment.upper()}")
        self.stdout.write(f"Database    : {database_name}")
        self.stdout.write("Tenant data : NONE")
        self.stdout.write("Company data: NONE")
        self.stdout.write("Seed data   : NONE")
