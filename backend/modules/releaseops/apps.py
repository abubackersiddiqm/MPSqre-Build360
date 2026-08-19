from django.apps import AppConfig


class ReleaseOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.releaseops"
    verbose_name = "Deployment, UAT and Release Operations"
