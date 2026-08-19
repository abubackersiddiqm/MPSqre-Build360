import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import {
  BrandDomainWorkspace,
  type BrandAssetCandidate,
  type BrandProfile,
  type Company,
  type DomainList,
  type EmailDeliveryProfile,
  type OnboardingSummary,
} from "./workspace";

export const metadata: Metadata = { title: "Brand, onboarding & domains" };
type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };
type ListResponse<T> = { items: T[] };

export default async function BrandDomainPage() {
  const [companyResult, capabilityResult] = await Promise.all([
    tenantBackendRequest<Company>("/companies/current"),
    tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities"),
  ]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status;
    redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  const features = capabilityResult.data.features ?? {};
  const whiteLabel = features["tenant.white_label"] === true;
  const customDomain = features["tenant.custom_domain"] === true;
  if ((!permissions.includes("tenant.branding.read") || !whiteLabel) && (!permissions.includes("tenant.domain.read") || !customDomain)) redirect("/platform");

  const [branding, domains, onboarding, assets, emailDelivery] = await Promise.all([
    permissions.includes("tenant.branding.read") && whiteLabel
      ? tenantBackendRequest<BrandProfile>("/companies/current/branding")
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("tenant.domain.read") && customDomain
      ? tenantBackendRequest<DomainList>("/companies/current/domains")
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("tenant.branding.read") && whiteLabel
      ? tenantBackendRequest<OnboardingSummary>("/companies/current/onboarding")
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("tenant.branding.read") && whiteLabel
      ? tenantBackendRequest<ListResponse<BrandAssetCandidate>>("/companies/current/branding/assets")
      : Promise.resolve({ ok: false as const, status: 403 }),
    permissions.includes("tenant.branding.read") && whiteLabel
      ? tenantBackendRequest<EmailDeliveryProfile>("/companies/current/email-delivery")
      : Promise.resolve({ ok: false as const, status: 403 }),
  ]);

  return (
    <BrandDomainWorkspace
      company={companyResult.data}
      permissions={permissions}
      features={features}
      initialBranding={branding.ok ? branding.data : null}
      initialDomains={domains.ok ? domains.data : { items: [], platform_domain_suffix: "", custom_domain_cname_target: "" }}
      initialOnboarding={onboarding.ok ? onboarding.data : null}
      initialAssets={assets.ok ? assets.data.items : []}
      initialEmailDelivery={emailDelivery.ok ? emailDelivery.data : null}
    />
  );
}
