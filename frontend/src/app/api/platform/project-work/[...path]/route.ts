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

  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  let response: Response;
  try {
    response = await fetch(
      backendUrl(`/project-work/${segments.map(encodeURIComponent).join("/")}`),
      { method: request.method, headers, body, cache: "no-store" },
    );
  } catch {
    return NextResponse.json(
      {
        message:
          "The Project & Work backend is unavailable. Restart Django and verify the backend API URL.",
      },
      { status: 502 },
    );
  }

  const responseBody = await response.arrayBuffer();
  if (response.status === 403) {
    const isOverview = segments.join("/") === "overview";
    return NextResponse.json(
      {
        detail: isOverview
          ? "Your current company role is missing work.view. Apply the Phase 30 v0.30.1 access repair, run its migration, and sign in again."
          : "Your current company role does not have the required Project & Work permission for this action.",
        upstream_status: response.status,
      },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
