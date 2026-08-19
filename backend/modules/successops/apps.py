from django.apps import AppConfig


class SuccessopsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.successops"
    verbose_name = "Customer Success and Billing Operations"

    def ready(self) -> None:
        from modules.successops import checks  # noqa: F401
