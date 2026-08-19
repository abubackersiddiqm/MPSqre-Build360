import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { Project360Workspace, type Company, type Project } from "./workspace";

export const metadata: Metadata = { title: "Project 360" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function Project360Page({ searchParams }: Readonly<{ searchParams: Promise<{ project?: string }> }>) {
  const [companyResult, capabilityResult, query] = await Promise.all([
    tenantBackendRequest<Company>("/companies/current"),
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
    searchParams,
  ]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status; redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("project.dashboard.read")) redirect("/platform");
  const projects = permissions.includes("project.project.read") ? await tenantBackendRequest<ListResponse<Project>>("/projects/items?limit=100") : { ok: true as const, status: 200, data: { items: [] } };
  return <Project360Workspace company={companyResult.data} initialProject={query.project ?? ""} initialProjects={projects.ok ? projects.data.items : []} permissions={permissions} />;
}
