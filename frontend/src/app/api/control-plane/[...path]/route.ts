import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
} from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const method = request.method.toUpperCase();
  if (!["GET", "HEAD"].includes(method) && !assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "CONTROLPLANE-ORIGIN-REJECTED", message: "Invalid request origin." },
      { status: 403 },
    );
  }
  const [token, params] = await Promise.all([accessToken(), context.params]);
  if (!token) {
    return NextResponse.json(
      { code: "CONTROLPLANE-AUTH-REQUIRED", message: "Authentication is required." },
      { status: 401 },
    );
  }
  const path = `/control-plane/${params.path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers({
    Accept: request.headers.get("accept") ?? "application/json",
    Authorization: `Bearer ${token}`,
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
    return new NextResponse(responseBody.byteLength ? responseBody : null, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "X-Request-Id": response.headers.get("X-Request-Id") ?? "",
      },
    });
  } catch (error) {
    console.error("Build360 SaaS control plane backend is unavailable", {
      error: error instanceof Error ? error.message : "Unknown backend connection error",
    });
    return NextResponse.json(
      {
        code: "CONTROLPLANE-BACKEND-UNAVAILABLE",
        message: "SaaS control plane service is unavailable. Confirm Django is running.",
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
