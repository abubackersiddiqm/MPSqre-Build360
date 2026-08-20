import "server-only";

import { cache } from "react";
import { headers } from "next/headers";

import { backendUrl } from "@/lib/auth/server-session";
import { normalizeRequestHost, shouldResolveTenantDomainBrand } from "./domain-host";

export type DomainBrand = {
  company: {
    public_id: string;
    code: string;
    display_name: string;
  };
  domain: {
    domain: string;
    domain_type: string;
    is_primary: boolean;
    ssl_status: string;
  };
  branding: {
    product_name: string;
    tagline: string;
    logo_url: string;
    compact_logo_url: string;
    favicon_url: string;
    login_background_url: string;
    primary_color: string;
    accent_color: string;
    powered_by_build360: boolean;
  };
};

export const domainBrandForCurrentHost = cache(async (): Promise<DomainBrand | null> => {
  const headerStore = await headers();
  const rawHost = headerStore.get("x-forwarded-host") ?? headerStore.get("host") ?? "";
  const host = normalizeRequestHost(rawHost);

  if (
    !shouldResolveTenantDomainBrand(host, {
      build360PublicWebUrl: process.env.BUILD360_PUBLIC_WEB_URL,
      vercelUrl: process.env.VERCEL_URL,
      vercelProjectProductionUrl: process.env.VERCEL_PROJECT_PRODUCTION_URL,
    })
  ) {
    return null;
  }

  let response: Response;
  try {
    response = await fetch(
      backendUrl(`/companies/domain/resolve?host=${encodeURIComponent(host)}`),
      { cache: "no-store" },
    );
  } catch (error: unknown) {
    console.error("[Build360 domain resolver] request failed", {
      host,
      error: error instanceof Error ? error.message : "unknown error",
    });
    return null;
  }

  if (response.status === 404) return null;

  if (!response.ok) {
    console.error("[Build360 domain resolver] unexpected response", {
      host,
      status: response.status,
    });
    return null;
  }

  return (await response.json()) as DomainBrand;
});
