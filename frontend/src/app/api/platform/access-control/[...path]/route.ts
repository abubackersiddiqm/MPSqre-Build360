import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
  platformAccessToken,
  selectedCompany,
} from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  if (!["GET", "HEAD"].includes(request.method) && !assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const { path } = await context.params;
  const segments = path ?? [];
  const invitationAction = segments[1];
  const isPublicInvitationRoute =
    segments.length === 2
    && segments[0] === "invitations"
    && invitationAction !== undefined
    && ["accept", "preview"].includes(invitationAction);
  const token = segments[0] === "platform" ? await platformAccessToken() : await accessToken();
  if (!isPublicInvitationRoute && !token) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }

  const headers = new Headers();
  headers.set("Accept", "application/json");
  headers.set("X-Request-Id", crypto.randomUUID());
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (request.headers.get("content-type")) {
    headers.set("Content-Type", request.headers.get("content-type") as string);
  }
  if (segments[0] === "company") {
    const companyPublicId = await selectedCompany();
    if (!companyPublicId) {
      return NextResponse.json({ message: "Tenant context required." }, { status: 401 });
    }
    headers.set("X-Company-Id", companyPublicId);
  }

  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : await request.arrayBuffer();
  const search = request.nextUrl.search || "";
  const backendResponse = await fetch(
    backendUrl(`/access-control/${segments.map(encodeURIComponent).join("/")}${search}`),
    {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    },
  );
  const responseBody = await backendResponse.arrayBuffer();
  return new NextResponse(responseBody, {
    status: backendResponse.status,
    headers: {
      "Content-Type": backendResponse.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
