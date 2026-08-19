import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };
const roots: Record<string, string> = {
  reporting: "reporting",
  portal: "portal",
  dataops: "dataops",
};

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method) && !assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "OPERATIONS-ORIGIN-REJECTED", message: "Invalid request origin." },
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
      {
        code: "OPERATIONS-AUTH-REQUIRED",
        message: "Authentication and company selection are required.",
      },
      { status: 401 },
    );
  }
  const scope = params.path[0];
  const rest = params.path.slice(1);
  if (!scope) {
    return NextResponse.json({ message: "Operations route was not found." }, { status: 404 });
  }
  const root = roots[scope];
  if (!root) {
    return NextResponse.json({ message: "Operations route was not found." }, { status: 404 });
  }
  const path = `/${root}/${rest.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers({
    Accept: request.headers.get("accept") ?? "application/json",
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
  try {
    const response = await fetch(backendUrl(path), {
      method,
      headers,
      body,
      cache: "no-store",
    });
    const responseBody = await response.arrayBuffer();
    const responseHeaders = new Headers();
    for (const name of ["content-type", "content-disposition", "cache-control", "x-content-type-options"]) {
      const value = response.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("X-Request-Id", response.headers.get("X-Request-Id") ?? "");
    return new NextResponse(responseBody.byteLength ? responseBody : null, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("Build360 operations backend is unavailable", {
      error: error instanceof Error ? error.message : "Unknown backend connection error",
    });
    return NextResponse.json(
      {
        code: "OPERATIONS-BACKEND-UNAVAILABLE",
        message: "Operations service is unavailable. Confirm the Django API is running.",
      },
      { status: 503 },
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
