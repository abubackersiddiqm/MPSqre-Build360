import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
  selectedCompany,
} from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  if (!["GET", "HEAD"].includes(request.method) && !assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const token = await accessToken();
  if (!token) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }
  const companyPublicId = await selectedCompany();
  if (!companyPublicId) {
    return NextResponse.json({ message: "Tenant context required." }, { status: 401 });
  }
  const { path } = await context.params;
  const segments = path ?? [];
  const headers = new Headers();
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("X-Company-Id", companyPublicId);
  headers.set("X-Request-Id", crypto.randomUUID());
  if (request.headers.get("content-type")) {
    headers.set("Content-Type", request.headers.get("content-type") as string);
  }
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const response = await fetch(
    backendUrl(`/people-organization/${segments.map(encodeURIComponent).join("/")}`),
    { method: request.method, headers, body, cache: "no-store" },
  );
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
