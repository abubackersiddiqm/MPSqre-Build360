import { NextRequest, NextResponse } from "next/server";

import { assertSameOrigin, backendUrl } from "@/lib/auth/server-session";

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const body = await request.json().catch(() => null);
  const backendResponse = await fetch(backendUrl("/auth/password-reset/confirm"), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-Id": crypto.randomUUID() },
    body: JSON.stringify(body),
    cache: "no-store",
  }).catch(() => null);
  if (!backendResponse) {
    return NextResponse.json({ message: "Password recovery service is unavailable." }, { status: 503 });
  }
  const payload: unknown = await backendResponse.json().catch(() => ({ message: "The request could not be completed." }));
  return NextResponse.json(payload, { status: backendResponse.status });
}
