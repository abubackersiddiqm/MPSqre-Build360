import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method) && !assertSameOrigin(request)) {
    return NextResponse.json({ code: "BRAND-ORIGIN-REJECTED", message: "Invalid request origin." }, { status: 403 });
  }
  const [token, companyPublicId, params] = await Promise.all([accessToken(), selectedCompany(), context.params]);
  if (!token || !companyPublicId) {
    return NextResponse.json({ code: "BRAND-AUTH-REQUIRED", message: "Authentication and company selection are required." }, { status: 401 });
  }
  const joined = params.path.map(encodeURIComponent).join("/");
  let path: string;
  if (joined === "branding") path = "/companies/current/branding";
  else if (joined === "email-delivery") path = "/companies/current/email-delivery";
  else if (joined === "email-delivery/test") path = "/companies/current/email-delivery/test";
  else if (joined === "branding/assets") path = "/companies/current/branding/assets";
  else if (joined === "branding/assets/attach") path = "/companies/current/branding/assets/attach";
  else if (joined === "onboarding") path = "/companies/current/onboarding";
  else path = `/companies/current/domains${joined === "domains" ? "" : `/${joined.replace(/^domains\/?/, "")}`}`;
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Company-Id": companyPublicId,
    "X-Request-Id": crypto.randomUUID(),
  });
  let body: string | undefined;
  if (!["GET", "HEAD"].includes(method)) {
    body = await request.text();
    if (body) headers.set("Content-Type", request.headers.get("content-type") ?? "application/json");
  }
  const response = await fetch(backendUrl(path), { method, headers, body, cache: "no-store" }).catch(() => null);
  if (!response) return NextResponse.json({ message: "Branding service is unavailable." }, { status: 503 });
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(request: NextRequest, context: RouteContext) { return proxy(request, context); }
export async function POST(request: NextRequest, context: RouteContext) { return proxy(request, context); }
export async function PATCH(request: NextRequest, context: RouteContext) { return proxy(request, context); }
