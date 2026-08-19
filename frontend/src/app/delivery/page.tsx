import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import {
  DeliveryWorkspace,
  type DesignDocument,
  type DesignSummary,
  type Estimate,
  type EstimationSummary,
  type Project,
  type ProjectSummary,
  type PortalGrant,
} from "./delivery-workspace";

export const metadata: Metadata = { title: "Project delivery workspace" };

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  currency: string;
  timezone: string;
};

type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

type PageProps = { searchParams: Promise<{ tab?: string; project?: string }> };

export default async function DeliveryPage({ searchParams }: Readonly<PageProps>) {
  const query = await searchParams;
  const [companyResult, capabilityResult] = await Promise.all([
    tenantBackendRequest<Company>("/companies/current"),
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
  ]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status;
    redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("project.dashboard.read")) redirect("/platform");

  const [projectSummary, designSummary, estimationSummary, projects, documents, estimates, portalGrants] =
    await Promise.all([
      tenantBackendRequest<ProjectSummary>("/projects/summary"),
      permissions.includes("design.dashboard.read")
        ? tenantBackendRequest<DesignSummary>("/design/summary")
        : Promise.resolve({
            ok: true as const,
            status: 200,
            data: {
              documents: 0,
              versions: 0,
              issued_versions: 0,
              open_issues: 0,
              pending_reviews: 0,
            },
          }),
      permissions.includes("estimation.dashboard.read")
        ? tenantBackendRequest<EstimationSummary>("/estimation/summary")
        : Promise.resolve({
            ok: true as const,
            status: 200,
            data: {
              estimates: 0,
              versions: 0,
              baselined_versions: 0,
              baselined_value: "0",
              currency: companyResult.data.currency,
            },
          }),
      permissions.includes("project.project.read")
        ? tenantBackendRequest<ListResponse<Project>>("/projects/items?limit=100")
        : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
      permissions.includes("design.document.read")
        ? tenantBackendRequest<ListResponse<DesignDocument>>("/design/documents?limit=100")
        : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
      permissions.includes("estimation.estimate.read")
        ? tenantBackendRequest<ListResponse<Estimate>>("/estimation/estimates?limit=100")
        : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
      permissions.includes("portal.grant.read")
        ? tenantBackendRequest<ListResponse<PortalGrant>>("/portal/grants")
        : Promise.resolve({ ok: true as const, status: 200, data: { items: [] } }),
    ]);

  if (!projectSummary.ok) {
    redirect(projectSummary.status === 401 ? "/sign-in" : "/platform");
  }

  return (
    <DeliveryWorkspace
      company={companyResult.data}
      defaultTab={query.tab}
      initialProject={query.project ?? ""}
      initialDesignSummary={
        designSummary.ok
          ? designSummary.data
          : {
              documents: 0,
              versions: 0,
              issued_versions: 0,
              open_issues: 0,
              pending_reviews: 0,
            }
      }
      initialDocuments={documents.ok ? documents.data.items : []}
      initialEstimates={estimates.ok ? estimates.data.items : []}
      initialEstimationSummary={
        estimationSummary.ok
          ? estimationSummary.data
          : {
              estimates: 0,
              versions: 0,
              baselined_versions: 0,
              baselined_value: "0",
              currency: companyResult.data.currency,
            }
      }
      initialProjectSummary={projectSummary.data}
      initialProjects={projects.ok ? projects.data.items : []}
      initialPortalGrants={portalGrants.ok ? portalGrants.data.items : []}
      permissions={permissions}
    />
  );
}
