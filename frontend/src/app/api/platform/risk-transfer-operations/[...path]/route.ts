import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  if (!["GET", "HEAD"].includes(request.method) && !assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const token = await accessToken();
  if (!token) return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  const companyPublicId = await selectedCompany();
  if (!companyPublicId) return NextResponse.json({ message: "Tenant context required." }, { status: 401 });
  const { path } = await context.params;
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Company-Id": companyPublicId,
    "X-Request-Id": crypto.randomUUID(),
  });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const response = await fetch(
    backendUrl(`/risk-transfer-operations/${(path ?? []).map(encodeURIComponent).join("/")}`),
    { method: request.method, headers, body, cache: "no-store" },
  );
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
      "X-Upstream-Response-Time-Ms": response.headers.get("x-response-time-ms") ?? "",
      "Server-Timing": response.headers.get("server-timing") ?? "",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
