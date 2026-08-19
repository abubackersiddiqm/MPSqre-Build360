import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { HandoverBoardWorkspace, type Project } from "./workspace";
export const metadata: Metadata = { title: "Project handover readiness" };
type CapabilityResponse = { permissions: string[] }; type ListResponse<T> = { items: T[] };
export default async function Page({ searchParams }: Readonly<{ searchParams: Promise<{ project?: string }> }>) {
  const [capabilities, params] = await Promise.all([tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"), searchParams]);
  if (!capabilities.ok) redirect(capabilities.status === 401 ? "/sign-in" : "/select-company");
  const p = capabilities.data.permissions;
  if (!p.includes("project.dashboard.read") || (!p.includes("digitaltwin.view") && !p.includes("digitaltwin.handover"))) redirect("/project360");
  const projects = await tenantBackendRequest<ListResponse<Project>>("/projects/items?limit=100");
  return <HandoverBoardWorkspace initialProject={params.project ?? ""} initialProjects={projects.ok ? projects.data.items : []} />;
}
