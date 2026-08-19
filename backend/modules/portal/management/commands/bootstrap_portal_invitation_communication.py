from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.communication.models import CommunicationChannel, MessageTemplate
from modules.tenant.models import Company, Membership


class Command(BaseCommand):
    help = "Create a default published portal invitation email template when none exists."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", required=True)

    def handle(self, *args, **options):
        company = Company.objects.filter(code=options["company_code"].strip().upper()).first()
        if company is None:
            raise CommandError("Company was not found")
        membership = (
            Membership.objects.select_related("user")
            .filter(
                company=company,
                suspended_at__isnull=True,
                terminated_at__isnull=True,
                user__is_active=True,
            )
            .order_by("id")
            .first()
        )
        if membership is None:
            raise CommandError("An active company membership is required to own the template audit identity")
        existing = MessageTemplate.objects.filter(
            company=company,
            channel=CommunicationChannel.EMAIL,
            purpose_code="portal_invitation",
            status=MessageTemplate.Status.PUBLISHED,
        ).order_by("-version").first()
        if existing:
            self.stdout.write(self.style.SUCCESS(
                f"Published portal invitation template already exists: {existing.code} v{existing.version}"
            ))
            return
        template = MessageTemplate(
            company=company,
            code="PORTAL_INVITATION_EMAIL",
            name="Portal invitation",
            channel=CommunicationChannel.EMAIL,
            locale=company.locale or "en",
            version=1,
            status=MessageTemplate.Status.PUBLISHED,
            subject_template="{company_name} portal invitation",
            body_template=(
                "You have been invited to the {portal_type} portal for {company_name}.\\n\\n"
                "Sign in using {invited_email} and open:\\n{accept_url}\\n\\n"
                "This invitation expires at {expires_at}.\\n"
                "Support: {support_email}"
            ),
            variable_names=[
                "company_name",
                "portal_type",
                "invited_email",
                "accept_url",
                "expires_at",
                "support_email",
            ],
            purpose_code="portal_invitation",
            created_by_public_id=membership.user.public_id,
            published_by_public_id=membership.user.public_id,
            published_at=timezone.now(),
        )
        template.full_clean()
        template.save()
        self.stdout.write(self.style.SUCCESS(
            "Published PORTAL_INVITATION_EMAIL created. Existing communication policy/provider still govern delivery."
        ))
