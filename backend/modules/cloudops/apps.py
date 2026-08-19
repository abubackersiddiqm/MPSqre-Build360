from django.apps import AppConfig


class CloudopsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.cloudops"
    verbose_name = "Cloud deployment operations"

    def ready(self) -> None:
        from modules.cloudops import checks  # noqa: F401
