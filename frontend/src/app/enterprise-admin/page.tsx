import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  EnterpriseAdminWorkspace,
  type AdminopsSummary,
  type Company,
  type FeatureFlag,
  type HealthSnapshot,
  type Incident,
  type MaintenanceWindow,
  type ReleaseRecord,
  type Runbook,
  type RuntimeEnvironment,
  type ServiceObjective,
} from "./workspace";

export const metadata: Metadata = { title: "Enterprise administration and reliability" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function EnterpriseAdminPage() {
  const company = await tenantBackendRequest<Company>("/companies/current");
  if (!company.ok) redirect(company.status === 401 ? "/sign-in" : "/select-company");
  const capabilities = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilities.ok) {
    redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilities.data.permissions;
  if (!permissions.includes("adminops.dashboard.read")) redirect("/platform");

  const [summary, environments, releases, objectives, health, incidents, runbooks, flags, maintenance] =
    await Promise.all([
      tenantBackendRequest<AdminopsSummary>("/adminops/summary"),
      tenantBackendRequest<ListResponse<RuntimeEnvironment>>("/adminops/environments"),
      tenantBackendRequest<ListResponse<ReleaseRecord>>("/adminops/releases"),
      tenantBackendRequest<ListResponse<ServiceObjective>>("/adminops/objectives"),
      tenantBackendRequest<ListResponse<HealthSnapshot>>("/adminops/health"),
      tenantBackendRequest<ListResponse<Incident>>("/adminops/incidents"),
      tenantBackendRequest<ListResponse<Runbook>>("/adminops/runbooks"),
      tenantBackendRequest<ListResponse<FeatureFlag>>("/adminops/flags"),
      tenantBackendRequest<ListResponse<MaintenanceWindow>>("/adminops/maintenance"),
    ]);

  return (
    <EnterpriseAdminWorkspace
      company={company.data}
      permissions={permissions}
      initialSummary={summary.ok ? summary.data : null}
      initialEnvironments={environments.ok ? environments.data.items : []}
      initialReleases={releases.ok ? releases.data.items : []}
      initialObjectives={objectives.ok ? objectives.data.items : []}
      initialHealth={health.ok ? health.data.items : []}
      initialIncidents={incidents.ok ? incidents.data.items : []}
      initialRunbooks={runbooks.ok ? runbooks.data.items : []}
      initialFlags={flags.ok ? flags.data.items : []}
      initialMaintenance={maintenance.ok ? maintenance.data.items : []}
    />
  );
}
