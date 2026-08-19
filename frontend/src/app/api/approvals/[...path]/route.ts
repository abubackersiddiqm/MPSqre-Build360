import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
  selectedCompany,
} from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

function backendPath(parts: string[]): string | null {
  if (parts.length === 1 && parts[0] === "center") {
    return "/workflow/approval-center";
  }
  const resourcePublicId = parts[1];
  if (!resourcePublicId) return null;
  if (parts.length === 3 && parts[0] === "workflow" && parts[2] === "decision") {
    return `/workflow/approvals/${encodeURIComponent(resourcePublicId)}/decision`;
  }
  if (parts.length === 3 && parts[0] === "design" && parts[2] === "decision") {
    return `/design/reviews/${encodeURIComponent(resourcePublicId)}/decide`;
  }
  return null;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method) && !assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "APPROVALS-ORIGIN-REJECTED", message: "Invalid request origin." },
      { status: 403 },
    );
  }
  const [token, companyPublicId, params] = await Promise.all([
    accessToken(),
    selectedCompany(),
    context.params,
  ]);
  if (!token || !companyPublicId) {
    return NextResponse.json(
      { code: "APPROVALS-AUTH-REQUIRED", message: "Authentication and company selection are required." },
      { status: 401 },
    );
  }
  const path = backendPath(params.path);
  if (!path) {
    return NextResponse.json(
      { code: "APPROVALS-ROUTE-NOT-FOUND", message: "Approval route is not available." },
      { status: 404 },
    );
  }
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Company-Id": companyPublicId,
    "X-Request-Id": crypto.randomUUID(),
  });
  let body: string | undefined;
  if (!["GET", "HEAD"].includes(method)) {
    body = await request.text();
    if (body) {
      headers.set("Content-Type", request.headers.get("content-type") ?? "application/json");
    }
  }
  const response = await fetch(backendUrl(path), {
    method,
    headers,
    body,
    cache: "no-store",
  }).catch(() => null);
  if (!response) {
    return NextResponse.json(
      { code: "APPROVALS-BACKEND-UNAVAILABLE", message: "Approval service is unavailable." },
      { status: 503 },
    );
  }
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "X-Request-Id": response.headers.get("X-Request-Id") ?? "",
    },
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
