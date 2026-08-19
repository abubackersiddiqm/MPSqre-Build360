import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
  clearSessionCookies,
} from "@/lib/auth/server-session";

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const token = await accessToken();
  if (token) {
    await fetch(backendUrl("/auth/logout"), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify({ reason_code: "user_logout" }),
      cache: "no-store",
    }).catch(() => undefined);
  }
  const response = new NextResponse(null, { status: 204 });
  clearSessionCookies(response);
  return response;
}

