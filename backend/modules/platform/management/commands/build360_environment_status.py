from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser


class Command(BaseCommand):
    help = "Show the active Build360 environment, version and database target without exposing secrets."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--require",
            choices=["development", "testing", "demo", "production"],
            help="Fail unless the active environment matches the requested value.",
        )

    def handle(self, *args: object, **options: object) -> None:
        environment = str(settings.BUILD360_ENVIRONMENT)
        required = options.get("require")
        if required and environment != required:
            raise CommandError(
                f"Environment guard failed: expected {required}, active {environment}."
            )

        database = settings.DATABASES["default"]
        self.stdout.write("BUILD360 ENVIRONMENT STATUS")
        self.stdout.write(f"Environment : {environment.upper()}")
        self.stdout.write(f"Version     : v{settings.APP_VERSION}")
        self.stdout.write(f"Debug       : {settings.DEBUG}")
        self.stdout.write(f"DB engine   : {database.get('ENGINE', '')}")
        self.stdout.write(f"DB host     : {database.get('HOST', '') or 'local/sqlite'}")
        self.stdout.write(f"DB port     : {database.get('PORT', '') or '-'}")
        self.stdout.write(f"DB name     : {database.get('NAME', '')}")
        self.stdout.write(
            f"Env file    : {getattr(settings, 'ENV_FILE_PATH', None) or 'process variables only'}"
        )
        self.stdout.write(self.style.SUCCESS("Environment guard is valid."))
