import "server-only";

import { cache } from "react";
import { headers } from "next/headers";

import { backendUrl } from "@/lib/auth/server-session";

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
  const host = rawHost.split(",", 1)[0]?.trim().split(":", 1)[0]?.toLowerCase() ?? "";
  if (!host || host === "localhost" || host === "127.0.0.1") return null;

  try {
    const response = await fetch(
      backendUrl(`/companies/domain/resolve?host=${encodeURIComponent(host)}`),
      { cache: "no-store" },
    );
    return response.ok ? ((await response.json()) as DomainBrand) : null;
  } catch {
    return null;
  }
});
