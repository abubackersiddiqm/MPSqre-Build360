import { NextRequest, NextResponse } from "next/server";

import { assertSameOrigin, backendUrl } from "@/lib/auth/server-session";

type BackendPayload = {
  message?: string;
  debug_uid?: string;
  debug_token?: string;
};

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const body = await request.json().catch(() => null);
  const backendResponse = await fetch(backendUrl("/auth/password-reset/request"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": crypto.randomUUID(),
      "X-Build360-Public-Host": request.nextUrl.hostname,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  }).catch(() => null);
  if (!backendResponse) {
    return NextResponse.json({ message: "Password recovery service is unavailable." }, { status: 503 });
  }
  const payload = (await backendResponse.json().catch(() => ({}))) as BackendPayload;
  const responsePayload: { message?: string; development_reset_url?: string } = {
    message: payload.message,
  };
  if (payload.debug_uid && payload.debug_token) {
    responsePayload.development_reset_url = `${request.nextUrl.origin}/reset-password?uid=${encodeURIComponent(payload.debug_uid)}&token=${encodeURIComponent(payload.debug_token)}`;
  }
  return NextResponse.json(responsePayload, { status: backendResponse.status });
}
