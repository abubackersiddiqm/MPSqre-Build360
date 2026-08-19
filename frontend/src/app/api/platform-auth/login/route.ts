import { NextRequest, NextResponse } from "next/server";

import {
  assertSameOrigin,
  backendUrl,
  setPlatformTokenCookies,
  type TokenResponse,
} from "@/lib/auth/server-session";

type BackendErrorEnvelope = {
  code?: string;
  message?: string;
  request_id?: string;
};

type PlatformSessionResponse = {
  is_platform_operator?: boolean;
  operator?: {
    public_id?: string;
    operator_type_code?: string;
  } | null;
};

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "AUTH-ORIGIN-REJECTED", message: "Invalid request origin." },
      { status: 403 },
    );
  }

  const body: unknown = await request.json().catch(() => null);
  const backendResponse = await fetch(backendUrl("/auth/token"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": crypto.randomUUID(),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  }).catch(() => null);

  if (!backendResponse) {
    return NextResponse.json(
      { code: "AUTH-BACKEND-UNAVAILABLE", message: "Authentication service is unavailable." },
      { status: 503 },
    );
  }

  if (!backendResponse.ok) {
    const backendError = (await backendResponse.json().catch(() => ({}))) as BackendErrorEnvelope;
    return NextResponse.json(
      {
        code: backendError.code || `AUTH-${backendResponse.status}`,
        message:
          backendResponse.status === 401
            ? "Email or password is incorrect."
            : backendError.message || "Sign in could not be completed.",
      },
      { status: backendResponse.status },
    );
  }

  const tokens = (await backendResponse.json()) as TokenResponse;
  // Super Admin is governed by accessops.PlatformOperator.
  // Do not validate this login through controlplane.PlatformOperatorAssignment:
  // those are separate platform-operation assignments and are not the source of
  // truth for the /super-admin SaaS administration surface.
  const operatorResponse = await fetch(backendUrl("/access-control/platform/session"), {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
      "X-Request-Id": crypto.randomUUID(),
    },
    cache: "no-store",
  }).catch(() => null);

  if (!operatorResponse?.ok) {
    await fetch(backendUrl("/auth/logout"), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({ reason_code: "platform_operator_required" }),
      cache: "no-store",
    }).catch(() => undefined);
    return NextResponse.json(
      { message: "Platform Operator access is required for Super Administration." },
      { status: 403 },
    );
  }

  const operator = (await operatorResponse.json()) as PlatformSessionResponse;
  if (!operator.is_platform_operator) {
    await fetch(backendUrl("/auth/logout"), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({ reason_code: "platform_operator_required" }),
      cache: "no-store",
    }).catch(() => undefined);
    return NextResponse.json(
      { message: "Platform Operator access is required for Super Administration." },
      { status: 403 },
    );
  }

  const response = NextResponse.json({
    session_public_id: tokens.session_public_id,
    access_expires_at: tokens.access_expires_at,
  });
  setPlatformTokenCookies(response, tokens);
  return response;
}
