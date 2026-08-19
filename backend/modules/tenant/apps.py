from django.apps import AppConfig


class TenantConfig(AppConfig):
    name = "modules.tenant"
    label = "tenant"
    verbose_name = "Company and Tenant"

