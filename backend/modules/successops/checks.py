from django.core.checks import Error, register

from modules.successops.models import AdoptionSnapshot, SupportSlaPolicy


@register()
def successops_model_checks(app_configs, **kwargs):
    errors = []
    if SupportSlaPolicy.Severity.CRITICAL != "critical":
        errors.append(Error("Critical support severity contract changed", id="successops.E001"))
    company_field = AdoptionSnapshot._meta.get_field("company")
    if company_field.remote_field.related_name != "customer_success_adoption_snapshots":
        errors.append(
            Error(
                "Customer-success adoption snapshots require an isolated Company reverse accessor",
                id="successops.E002",
            )
        )
    return errors
