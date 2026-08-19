import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  OperationsWorkspace,
  type Company,
  type DataopsSummary,
  type ImportJob,
  type ImportTemplate,
  type Metric,
  type PortalGrant,
  type PortalInvitation,
  type PortalShare,
  type PortalSummary,
  type PrivacyRequest,
  type RecoveryVerification,
  type ReportingSummary,
  type ReportRun,
  type RetentionPolicy,
  type SavedReport,
} from "./workspace";

export const metadata: Metadata = { title: "Reports, portals and operations" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function OperationsPage() {
  const company = await tenantBackendRequest<Company>("/companies/current");
  if (!company.ok) redirect(company.status === 401 ? "/sign-in" : "/select-company");
  const capabilities = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilities.ok) {
    redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilities.data.permissions;
  if (!permissions.includes("reporting.dashboard.read")) redirect("/platform");

  const [
    reportingSummary,
    metrics,
    savedReports,
    reportRuns,
    portalSummary,
    invitations,
    grants,
    shares,
    dataopsSummary,
    templates,
    imports,
    privacy,
    retention,
    recovery,
  ] = await Promise.all([
    tenantBackendRequest<ReportingSummary>("/reporting/summary"),
    tenantBackendRequest<ListResponse<Metric>>("/reporting/metrics"),
    tenantBackendRequest<ListResponse<SavedReport>>("/reporting/saved"),
    tenantBackendRequest<ListResponse<ReportRun>>("/reporting/runs"),
    tenantBackendRequest<PortalSummary>("/portal/summary"),
    tenantBackendRequest<ListResponse<PortalInvitation>>("/portal/invitations"),
    tenantBackendRequest<ListResponse<PortalGrant>>("/portal/grants"),
    tenantBackendRequest<ListResponse<PortalShare>>("/portal/shares"),
    tenantBackendRequest<DataopsSummary>("/dataops/summary"),
    tenantBackendRequest<ListResponse<ImportTemplate>>("/dataops/templates"),
    tenantBackendRequest<ListResponse<ImportJob>>("/dataops/imports"),
    tenantBackendRequest<ListResponse<PrivacyRequest>>("/dataops/privacy"),
    tenantBackendRequest<ListResponse<RetentionPolicy>>("/dataops/retention"),
    tenantBackendRequest<ListResponse<RecoveryVerification>>("/dataops/recovery"),
  ]);

  return (
    <OperationsWorkspace
      company={company.data}
      permissions={permissions}
      initialReportingSummary={reportingSummary.ok ? reportingSummary.data : null}
      initialMetrics={metrics.ok ? metrics.data.items : []}
      initialSavedReports={savedReports.ok ? savedReports.data.items : []}
      initialReportRuns={reportRuns.ok ? reportRuns.data.items : []}
      initialPortalSummary={portalSummary.ok ? portalSummary.data : null}
      initialInvitations={invitations.ok ? invitations.data.items : []}
      initialGrants={grants.ok ? grants.data.items : []}
      initialShares={shares.ok ? shares.data.items : []}
      initialDataopsSummary={dataopsSummary.ok ? dataopsSummary.data : null}
      initialTemplates={templates.ok ? templates.data.items : []}
      initialImports={imports.ok ? imports.data.items : []}
      initialPrivacy={privacy.ok ? privacy.data.items : []}
      initialRetention={retention.ok ? retention.data.items : []}
      initialRecovery={recovery.ok ? recovery.data.items : []}
    />
  );
}
