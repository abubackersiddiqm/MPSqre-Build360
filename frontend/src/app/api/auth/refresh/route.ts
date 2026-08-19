import { NextRequest, NextResponse } from "next/server";

import {
  assertSameOrigin,
  backendUrl,
  clearSessionCookies,
  refreshToken,
  setTokenCookies,
  type TokenResponse,
} from "@/lib/auth/server-session";

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const token = await refreshToken();
  if (!token) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }
  const backendResponse = await fetch(backendUrl("/auth/refresh"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": crypto.randomUUID(),
    },
    body: JSON.stringify({ refresh_token: token }),
    cache: "no-store",
  });
  if (!backendResponse.ok) {
    const response = NextResponse.json(
      { message: "Session expired. Sign in again." },
      { status: 401 },
    );
    clearSessionCookies(response);
    return response;
  }
  const tokens = (await backendResponse.json()) as TokenResponse;
  const response = NextResponse.json({
    session_public_id: tokens.session_public_id,
    access_expires_at: tokens.access_expires_at,
  });
  setTokenCookies(response, tokens);
  return response;
}

