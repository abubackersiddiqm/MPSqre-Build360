import { NextResponse } from "next/server";

import { accessToken, backendUrl } from "@/lib/auth/server-session";

export async function GET() {
  const token = await accessToken();
  if (!token) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }
  const backendResponse = await fetch(backendUrl("/auth/me"), {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Request-Id": crypto.randomUUID(),
    },
    cache: "no-store",
  });
  const body: unknown = await backendResponse.json().catch(() => ({
    message: "The request could not be completed.",
  }));
  return NextResponse.json(body, { status: backendResponse.status });
}

