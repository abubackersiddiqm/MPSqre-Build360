import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

import { ProjectDesignWorkspace, type Project } from "./workspace";

export const metadata: Metadata = { title: "Visual design board" };

type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function ProjectDesignPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ project?: string; document?: string }> }>) {
  const [capabilityResult, params] = await Promise.all([
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
    searchParams,
  ]);
  if (!capabilityResult.ok) {
    redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  if (
    !permissions.includes("project.dashboard.read") ||
    !permissions.includes("design.document.read")
  ) {
    redirect("/project360");
  }
  const projects = await tenantBackendRequest<ListResponse<Project>>("/projects/items?limit=100");
  return (
    <ProjectDesignWorkspace
      initialDocument={params.document ?? ""}
      initialProject={params.project ?? ""}
      initialProjects={projects.ok ? projects.data.items : []}
    />
  );
}
