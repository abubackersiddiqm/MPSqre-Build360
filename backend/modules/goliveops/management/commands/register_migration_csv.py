from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from modules.goliveops.models import MigrationBatch
from modules.identity.models import User
from modules.tenant.models import Company


class Command(BaseCommand):
    help = "Register a CSV file as a governed Phase 35 migration batch. This command does not import domain records."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True)
        parser.add_argument("--code", required=True)
        parser.add_argument("--entity", required=True)
        parser.add_argument("--file", required=True)
        parser.add_argument("--actor-email", required=True)
        parser.add_argument("--commit", action="store_true", help="Mark the batch as a non-dry-run candidate.")

    def handle(self, *args, **options):
        path = Path(options["file"]).expanduser().resolve()
        if not path.is_file():
            raise CommandError(f"CSV file not found: {path}")
        company = Company.objects.filter(code=options["company"].strip()).first()
        if company is None:
            raise CommandError(f"Company not found: {options['company']}")
        actor = User.objects.filter(email__iexact=options["actor_email"].strip()).first()
        if actor is None:
            raise CommandError(f"User not found: {options['actor_email']}")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
        total_rows = max(0, len(rows) - 1)
        batch = MigrationBatch(
            company=company,
            code=options["code"],
            entity_code=options["entity"],
            source_file_name=path.name,
            source_checksum=checksum,
            dry_run=not options["commit"],
            total_rows=total_rows,
            valid_rows=0,
            invalid_rows=0,
            warning_rows=0,
            created_by_public_id=actor.public_id,
            notes="Registered through register_migration_csv. Domain import remains gated.",
        )
        batch.full_clean()
        batch.save()
        self.stdout.write(self.style.SUCCESS(f"Registered {batch.code}: rows={total_rows} sha256={checksum} public_id={batch.public_id}"))
