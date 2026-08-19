import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method) && !assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "ADMINOPS-ORIGIN-REJECTED", message: "Invalid request origin." },
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
        code: "ADMINOPS-AUTH-REQUIRED",
        message: "Authentication and company selection are required.",
      },
      { status: 401 },
    );
  }
  const path = `/adminops/${params.path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers({
    Accept: request.headers.get("accept") ?? "application/json",
    Authorization: `Bearer ${token}`,
    "X-Company-Id": companyPublicId,
    "X-Request-Id": crypto.randomUUID(),
  });
  let body: string | undefined;
  if (!["GET", "HEAD"].includes(method)) {
    body = await request.text();
    if (body) headers.set("Content-Type", request.headers.get("content-type") ?? "application/json");
  }
  try {
    const response = await fetch(backendUrl(path), {
      method,
      headers,
      body,
      cache: "no-store",
    });
    const responseBody = await response.arrayBuffer();
    return new NextResponse(responseBody.byteLength ? responseBody : null, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "X-Request-Id": response.headers.get("X-Request-Id") ?? "",
      },
    });
  } catch (error) {
    console.error("Build360 enterprise administration backend is unavailable", {
      error: error instanceof Error ? error.message : "Unknown backend connection error",
    });
    return NextResponse.json(
      {
        code: "ADMINOPS-BACKEND-UNAVAILABLE",
        message: "Enterprise administration service is unavailable. Confirm Django is running.",
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
