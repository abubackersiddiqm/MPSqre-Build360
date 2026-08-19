from django.urls import include, path

urlpatterns = [
    path("api/v1/risk-transfer-operations/", include("modules.risktransferops.api.urls")),
    path("api/v1/capital-investment-operations/", include("modules.capitalops.api.urls")),
    path("api/v1/land-acquisition-operations/", include("modules.landops.api.urls")),
    path("api/v1/development-sales-operations/", include("modules.salesops.api.urls")),
    path("api/v1/property-lease-operations/", include("modules.leaseops.api.urls")),
    path("api/v1/facilities-operations/", include("modules.facilityops.api.urls")),
    path("api/v1/digital-twin-operations/", include("modules.digitaltwinops.api.urls")),
    path("api/v1/sustainability-operations/", include("modules.sustainabilityops.api.urls")),
    path("api/v1/executive-intelligence/", include("modules.insightops.api.urls")),
    path("api/v1/support-operations/", include("modules.supportops.api.urls")),
    path("api/v1/go-live-operations/", include("modules.goliveops.api.urls")),
    path("api/v1/stability-operations/", include("modules.stabilityops.api.urls")),
    path("api/v1/release-readiness/", include("modules.releaseops.api.urls")),
    path("api/v1/external-collaboration/", include("modules.collabops.api.urls")),
    path("api/v1/my-work/", include("modules.myworkops.api.urls")),
    path("api/v1/project-work/", include("modules.workops.api.urls")),
    path("api/v1/people-organization/", include("modules.orgops.api.urls")),
    path("api/v1/access-control/", include("modules.accessops.api.urls")),
    path("api/v1/commercial-operations/", include("modules.commercialops.api.urls")),
    path("api/v1/document-control/", include("modules.documentops.api.urls")),
    path("api/v1/quality-operations/", include("modules.qualityops.api.urls")),
    path("api/v1/safety-operations/", include("modules.safetyops.api.urls")),
    path("api/v1/equipment-operations/", include("modules.equipmentops.api.urls")),
    path("api/v1/workforce-planning/", include("modules.workforceops.api.urls")),
    path("api/v1/payroll-operations/", include("modules.payrollops.api.urls")),
    path("api/v1/", include("modules.platform.api.urls")),
    path("api/v1/auth/", include("modules.identity.api.urls")),
    path("api/v1/companies/", include("modules.tenant.api.urls")),
    path("api/v1/configurations/", include("modules.configuration.api.urls")),
    path("api/v1/workflows/", include("modules.workflow.api.urls")),
    path("api/v1/subscriptions/", include("modules.subscription.api.urls")),
    path("api/v1/files/", include("modules.files.api.urls")),
    path("api/v1/crm/", include("modules.crm.api.urls")),
    path("api/v1/projects/", include("modules.projects.api.urls")),
    path("api/v1/design/", include("modules.design.api.urls")),
    path("api/v1/estimation/", include("modules.estimation.api.urls")),
    path("api/v1/vendors/", include("modules.vendor.api.urls")),
    path("api/v1/inventory/", include("modules.inventory.api.urls")),
    path("api/v1/procurement/", include("modules.procurement.api.urls")),
    path("api/v1/field/", include("modules.fieldops.api.urls")),
    path("api/v1/labour/", include("modules.labour.api.urls")),
    path("api/v1/equipment/", include("modules.equipment.api.urls")),
    path("api/v1/quality/", include("modules.quality.api.urls")),
    path("api/v1/safety/", include("modules.safety.api.urls")),
    path("api/v1/finance/", include("modules.finance.api.urls")),
    path("api/v1/communications/", include("modules.communication.api.urls")),
    path("api/v1/notifications/", include("modules.notifications.api.urls")),
    path("api/v1/reporting/", include("modules.reporting.api.urls")),
    path("api/v1/portal/", include("modules.portal.api.urls")),
    path("api/v1/dataops/", include("modules.dataops.api.urls")),
    path("api/v1/ai/", include("modules.ai.api.urls")),
    path("api/v1/adminops/", include("modules.adminops.api.urls")),
    path("api/v1/control-plane/", include("modules.controlplane.api.urls")),
    path("api/v1/integrations/", include("modules.integration.api.urls")),
    path("api/v1/pilotops/", include("modules.pilotops.api.urls")),
    path("api/v1/compliance/", include("modules.compliance.api.urls")),
    path("api/v1/cloudops/", include("modules.cloudops.api.urls")),
    path("api/v1/customer-success/", include("modules.successops.api.urls")),
    path("api/v1/people/", include("modules.peopleops.api.urls")),
]
