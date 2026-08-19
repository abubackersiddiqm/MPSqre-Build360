import { NextRequest, NextResponse } from "next/server";

import {
  accessToken,
  assertSameOrigin,
  backendUrl,
  setCompanyCookie,
} from "@/lib/auth/server-session";

type MembershipResponse = {
  memberships?: Array<{ company: { public_id: string } }>;
};

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json({ message: "Invalid request origin." }, { status: 403 });
  }
  const token = await accessToken();
  if (!token) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }
  const body = (await request.json().catch(() => null)) as {
    company_public_id?: unknown;
  } | null;
  if (!body || typeof body.company_public_id !== "string") {
    return NextResponse.json({ message: "A company is required." }, { status: 400 });
  }
  const meResponse = await fetch(backendUrl("/auth/me"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!meResponse.ok) {
    return NextResponse.json({ message: "Authentication required." }, { status: 401 });
  }
  const me = (await meResponse.json()) as MembershipResponse;
  const allowed = me.memberships?.some(
    (membership) => membership.company.public_id === body.company_public_id,
  );
  if (!allowed) {
    return NextResponse.json({ message: "Resource not found." }, { status: 404 });
  }
  const response = NextResponse.json({ selected: true });
  setCompanyCookie(response, body.company_public_id);
  return response;
}

