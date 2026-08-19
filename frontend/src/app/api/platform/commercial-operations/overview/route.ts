import { NextResponse } from "next/server";

import {
  accessToken,
  backendUrl,
  selectedCompany,
} from "@/lib/auth/server-session";

export const dynamic = "force-dynamic";

function upstreamMessage(status: number, fallback: string) {
  if (status === 404) {
    return "The commercial API route is not active. Restart the Django backend after applying Phase 27.";
  }
  if (status === 401) {
    return "Your Build360 session has expired. Sign in again and reopen Commercial Operations.";
  }
  if (status === 403) {
    return "The selected membership does not have commercial.view permission.";
  }
  if (status >= 500) {
    return "Commercial overview failed in the backend. Apply the Phase 27 repair and run all pending migrations.";
  }
  return fallback;
}

export async function GET() {
  const [token, companyPublicId] = await Promise.all([
    accessToken(),
    selectedCompany(),
  ]);

  if (!token || !companyPublicId) {
    return NextResponse.json(
      { message: "Authentication and tenant context are required." },
      { status: 401 },
    );
  }

  try {
    const backendResponse = await fetch(
      backendUrl("/commercial-operations/overview/"),
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Id": companyPublicId,
          "X-Request-Id": crypto.randomUUID(),
        },
        cache: "no-store",
      },
    );

    const rawBody = await backendResponse.text();
    let body: Record<string, unknown> = {};
    try {
      body = rawBody ? (JSON.parse(rawBody) as Record<string, unknown>) : {};
    } catch {
      body = {};
    }

    if (!backendResponse.ok) {
      const fallback =
        typeof body.message === "string"
          ? body.message
          : "Commercial operations could not be loaded.";
      return NextResponse.json(
        {
          ...body,
          message: upstreamMessage(backendResponse.status, fallback),
          upstream_status: backendResponse.status,
        },
        { status: backendResponse.status },
      );
    }

    return NextResponse.json(body, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      {
        message:
          "The commercial API is unreachable. Restart the Django backend and retry the workspace.",
      },
      { status: 502 },
    );
  }
}
