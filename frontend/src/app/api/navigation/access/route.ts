import { NextRequest, NextResponse } from "next/server";

import { accessToken, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type NavigationAccess = {
  is_platform_operator: boolean;
  can_manage_access: boolean;
  can_manage_people: boolean;
  can_use_my_work: boolean;
  can_use_partner_portal: boolean;
  permissions: string[];
  features: Record<string, boolean>;
};

type JsonRecord = Record<string, unknown>;

const EMPTY_ACCESS: NavigationAccess = {
  is_platform_operator: false,
  can_manage_access: false,
  can_manage_people: false,
  can_use_my_work: false,
  can_use_partner_portal: false,
  permissions: [],
  features: {},
};

async function backendProbe(path: string, token: string, companyPublicId: string | undefined): Promise<Response> {
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Request-Id": crypto.randomUUID(),
  });
  if (companyPublicId) headers.set("X-Company-Id", companyPublicId);
  return fetch(backendUrl(path), { method: "GET", headers, cache: "no-store" });
}

async function safeJson(response: Response): Promise<JsonRecord> {
  if (!response.ok) return {};
  return (await response.json().catch(() => ({}))) as JsonRecord;
}

function permissionList(payload: JsonRecord): string[] {
  const raw = payload.permissions;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is string => typeof item === "string");
}

function featureMap(payload: JsonRecord): Record<string, boolean> {
  const raw = payload.features;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return Object.fromEntries(
    Object.entries(raw).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean"),
  );
}

export async function GET(request: NextRequest) {
  const token = await accessToken();
  if (!token) return NextResponse.json({ message: "Authentication required." }, { status: 401 });

  const companyPublicId = await selectedCompany();
  const mode = request.nextUrl.searchParams.get("mode") === "partner" ? "partner" : "internal";

  if (mode === "partner") {
    if (!companyPublicId) {
      return NextResponse.json<NavigationAccess>(EMPTY_ACCESS, { headers: { "Cache-Control": "private, no-store" } });
    }
    const partnerResponse = await backendProbe("/external-collaboration/partner/overview", token, companyPublicId);
    return NextResponse.json<NavigationAccess>({
      ...EMPTY_ACCESS,
      can_use_partner_portal: partnerResponse.ok,
    }, { headers: { "Cache-Control": "private, no-store" } });
  }

  const [operatorResponse, capabilityResponse] = await Promise.all([
    backendProbe("/access-control/platform/session", token, companyPublicId),
    companyPublicId
      ? backendProbe("/companies/current/capabilities", token, companyPublicId)
      : Promise.resolve(new Response(null, { status: 401 })),
  ]);

  const operatorPayload = await safeJson(operatorResponse);
  const capabilityPayload = await safeJson(capabilityResponse);
  const permissions = permissionList(capabilityPayload);
  const permissionSet = new Set(permissions);

  return NextResponse.json<NavigationAccess>({
    is_platform_operator: Boolean(operatorPayload.is_platform_operator),
    can_manage_access: permissionSet.has("access.user.manage"),
    can_manage_people: permissionSet.has("peopleorg.view"),
    can_use_my_work: permissionSet.has("mywork.view"),
    can_use_partner_portal: false,
    permissions,
    features: featureMap(capabilityPayload),
  }, { headers: { "Cache-Control": "private, no-store" } });
}
