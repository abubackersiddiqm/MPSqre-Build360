from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.views import APIView

from modules.accessops.models import PlatformOperator
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.application.context import TenantContext, resolve_tenant_context

# Server-side SaaS module boundary. Navigation hiding is presentation only; tenant
# requests still pass through this map before domain permissions are evaluated.
TENANT_FEATURE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/v1/crm/", "crm.core"),
    ("/api/v1/projects/", "module.delivery"),
    ("/api/v1/design/", "module.delivery"),
    ("/api/v1/estimation/", "module.delivery"),
    ("/api/v1/project-work/", "module.delivery"),
    ("/api/v1/vendors/", "module.supply"),
    ("/api/v1/inventory/", "module.supply"),
    ("/api/v1/procurement/", "module.supply"),
    ("/api/v1/field/", "module.field"),
    ("/api/v1/labour/", "module.field"),
    ("/api/v1/equipment/", "module.equipment"),
    ("/api/v1/finance/", "module.finance"),
    ("/api/v1/communications/", "module.communication"),
    ("/api/v1/reporting/", "module.reporting"),
    ("/api/v1/dataops/", "module.reporting"),
    ("/api/v1/executive-intelligence/", "module.reporting"),
    ("/api/v1/ai/", "module.ai"),
    ("/api/v1/integrations/meta-leads", "crm.meta_ads"),
    ("/api/v1/integrations/", "module.integrations"),
    ("/api/v1/compliance/", "module.compliance"),
    ("/api/v1/people/", "module.people"),
    ("/api/v1/people-organization/", "module.people"),
    ("/api/v1/payroll-operations/", "module.payroll"),
    ("/api/v1/workforce-planning/", "module.workforce"),
    ("/api/v1/equipment-operations/", "module.equipment"),
    ("/api/v1/safety-operations/", "module.hse"),
    ("/api/v1/safety/", "module.hse"),
    ("/api/v1/quality-operations/", "module.quality"),
    ("/api/v1/quality/", "module.quality"),
    ("/api/v1/document-control/", "module.documents"),
    ("/api/v1/commercial-operations/", "module.commercial"),
    ("/api/v1/external-collaboration/", "module.partner"),
    ("/api/v1/portal/", "module.partner"),
    ("/api/v1/sustainability-operations/", "module.sustainability"),
    ("/api/v1/digital-twin-operations/", "module.digital_twin"),
    ("/api/v1/facilities-operations/", "module.facilities"),
    ("/api/v1/property-lease-operations/", "module.property"),
    ("/api/v1/development-sales-operations/", "module.sales"),
    ("/api/v1/land-acquisition-operations/", "module.land"),
    ("/api/v1/capital-investment-operations/", "module.capital"),
    ("/api/v1/risk-transfer-operations/", "module.risk_transfer"),
)

# These are Build360 operator/release surfaces, not tenant subscription modules.
PLATFORM_OPERATOR_PREFIXES: tuple[str, ...] = (
    "/api/v1/adminops/",
    "/api/v1/control-plane/",
    "/api/v1/pilotops/",
    "/api/v1/cloudops/",
    "/api/v1/customer-success/",
    "/api/v1/release-readiness/",
    "/api/v1/stability-operations/",
    "/api/v1/go-live-operations/",
    "/api/v1/support-operations/",
    "/api/v1/subscriptions/",
)


def _active_platform_operator(request: Request) -> bool:
    principal = getattr(request, "auth", None)
    user = getattr(principal, "user", None)
    if user is None:
        return False
    return PlatformOperator.objects.filter(user=user, is_active=True).exists()


class TenantScopedAPIView(APIView):
    tenant_context: TenantContext

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context = resolve_tenant_context(request)
        path = request.path

        if any(path.startswith(prefix) for prefix in PLATFORM_OPERATOR_PREFIXES):
            if not _active_platform_operator(request):
                raise PermissionDenied("This workspace is reserved for Build360 platform operators")
            return

        for prefix, feature_code in TENANT_FEATURE_PREFIXES:
            if path.startswith(prefix):
                if not feature_enabled(company=self.tenant_context.company, code=feature_code):
                    raise PermissionDenied(f"SaaS module is not enabled: {feature_code}")
                break
