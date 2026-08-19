import { NextResponse } from "next/server";

import { platformBackendRequest } from "@/lib/auth/platform-backend";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  branding?: {
    product_name: string; tagline: string; logo_url: string; compact_logo_url: string; favicon_url: string;
    primary_color: string; accent_color: string; sidebar_style: string; powered_by_build360: boolean; version: number;
  };
  primary_domain?: string | null;
};

type CapabilityResponse = { permissions: string[]; features: Record<string, boolean> };
type OperatorResponse = { is_operator: boolean };
type MeResponse = { memberships?: Array<{ company: { public_id: string } }> };
type NotificationSummary = {
  unread: number;
  critical_unread: number;
};

function build360Environment() {
  const value = (process.env.BUILD360_ENVIRONMENT || process.env.APP_ENV || "development").trim().toLowerCase();
  if (value === "test" || value === "testing") return "testing";
  if (value === "demo") return "demo";
  if (value === "production" || value === "prod") return "production";
  return "development";
}

export async function GET() {
  const companyResult = await tenantBackendRequest<Company>("/companies/current");
  if (!companyResult.ok) {
    return NextResponse.json(
      { message: "Company context is unavailable." },
      { status: companyResult.status },
    );
  }

  const capabilityResult = await tenantBackendRequest<CapabilityResponse>(
    "/companies/current/capabilities",
  );
  if (!capabilityResult.ok) {
    return NextResponse.json(
      { message: "Capabilities are unavailable." },
      { status: capabilityResult.status },
    );
  }

  const permissions = capabilityResult.data.permissions;
  const [operatorResult, meResult, notificationResult] = await Promise.all([
    platformBackendRequest<OperatorResponse>("/control-plane/me"),
    platformBackendRequest<MeResponse>("/auth/me"),
    permissions.includes("notification.dashboard.read")
      ? tenantBackendRequest<NotificationSummary>("/notifications/summary")
      : Promise.resolve({ ok: false as const, status: 403 }),
  ]);

  return NextResponse.json(
    {
      company: companyResult.data,
      permissions,
      features: capabilityResult.data.features ?? {},
      platform_operator: operatorResult.ok && operatorResult.data.is_operator,
      company_membership_count: meResult.ok ? (meResult.data.memberships?.length ?? 0) : 1,
      notifications: notificationResult.ok
        ? notificationResult.data
        : { unread: 0, critical_unread: 0 },
      environment: build360Environment(),
      version: (process.env.APP_VERSION || "1.0.0").trim() || "1.0.0",
    },
    {
      headers: {
        "Cache-Control": "private, no-store",
      },
    },
  );
}
