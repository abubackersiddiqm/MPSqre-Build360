import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl } from "@/lib/auth/server-session";

type BackendError = { message?: string; detail?: string; code?: string; request_id?: string };

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "PORTAL-ORIGIN-REJECTED", message: "Invalid request origin." },
      { status: 403 },
    );
  }
  const token = await accessToken();
  if (!token) {
    return NextResponse.json(
      { code: "PORTAL-AUTH-REQUIRED", message: "Sign in before accepting the invitation." },
      { status: 401 },
    );
  }
  const body: unknown = await request.json().catch(() => null);
  let backendResponse: Response;
  try {
    backendResponse = await fetch(backendUrl("/portal/invitations/accept"), {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (error) {
    console.error("Build360 portal invitation service is unavailable", {
      error: error instanceof Error ? error.message : "Unknown backend connection error",
    });
    return NextResponse.json(
      {
        code: "PORTAL-BACKEND-UNAVAILABLE",
        message: "Portal invitation service is unavailable. Confirm the Django API is running.",
      },
      { status: 503 },
    );
  }
  const responseBody = (await backendResponse.json().catch(() => ({}))) as BackendError;
  return NextResponse.json(responseBody, { status: backendResponse.status });
}
