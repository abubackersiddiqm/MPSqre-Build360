import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import {
  FieldOperationsWorkspace,
  type EquipmentAsset,
  type EquipmentSummary,
  type FieldSyncSummary,
  type Inspection,
  type LabourSummary,
  type QualitySummary,
  type SafetyIncident,
  type SafetySummary,
  type Worker,
} from "./workspace";

export const metadata: Metadata = { title: "Field operations" };

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  currency: string;
  timezone: string;
};
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };
type Project = { public_id: string; code: string; name: string };

export default async function FieldOperationsPage() {
  const [companyResult, capabilityResult] = await Promise.all([
    tenantBackendRequest<Company>("/companies/current"),
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
  ]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status;
    redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("field.dashboard.read")) {
    redirect("/platform");
  }

  const [
    labourSummary,
    equipmentSummary,
    qualitySummary,
    safetySummary,
    syncSummary,
    workers,
    assets,
    inspections,
    incidents,
    projects,
  ] = await Promise.all([
    tenantBackendRequest<LabourSummary>("/labour/summary"),
    tenantBackendRequest<EquipmentSummary>("/equipment/summary"),
    tenantBackendRequest<QualitySummary>("/quality/summary"),
    tenantBackendRequest<SafetySummary>("/safety/summary"),
    tenantBackendRequest<FieldSyncSummary>("/field/summary"),
    tenantBackendRequest<ListResponse<Worker>>("/labour/workers"),
    tenantBackendRequest<ListResponse<EquipmentAsset>>("/equipment/assets"),
    tenantBackendRequest<ListResponse<Inspection>>("/quality/inspections"),
    tenantBackendRequest<ListResponse<SafetyIncident>>("/safety/incidents"),
    tenantBackendRequest<ListResponse<Project>>("/projects/items"),
  ]);

  return (
    <FieldOperationsWorkspace
      company={companyResult.data}
      permissions={permissions}
      initialLabourSummary={labourSummary.ok ? labourSummary.data : null}
      initialEquipmentSummary={equipmentSummary.ok ? equipmentSummary.data : null}
      initialQualitySummary={qualitySummary.ok ? qualitySummary.data : null}
      initialSafetySummary={safetySummary.ok ? safetySummary.data : null}
      initialSyncSummary={syncSummary.ok ? syncSummary.data : null}
      initialWorkers={workers.ok ? workers.data.items : []}
      initialAssets={assets.ok ? assets.data.items : []}
      initialInspections={inspections.ok ? inspections.data.items : []}
      initialIncidents={incidents.ok ? incidents.data.items : []}
      projects={projects.ok ? projects.data.items : []}
    />
  );
}
