import { NextResponse } from "next/server";

import {
  accessToken,
  backendUrl,
  selectedCompany,
} from "@/lib/auth/server-session";

export async function GET() {
  const [token, companyPublicId] = await Promise.all([
    accessToken(),
    selectedCompany(),
  ]);
  if (!token || !companyPublicId) {
    return NextResponse.json({ message: "Tenant context required." }, { status: 401 });
  }
  const backendResponse = await fetch(backendUrl("/companies/current"), {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Company-Id": companyPublicId,
      "X-Request-Id": crypto.randomUUID(),
    },
    cache: "no-store",
  });
  const body: unknown = await backendResponse.json().catch(() => ({
    message: "The request could not be completed.",
  }));
  return NextResponse.json(body, { status: backendResponse.status });
}

