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
    return NextResponse.json(
      { message: "Authentication and tenant context are required." },
      { status: 401 },
    );
  }

  try {
    const backendResponse = await fetch(
      backendUrl("/payroll-operations/overview/"),
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Company-Id": companyPublicId,
          "X-Request-Id": crypto.randomUUID(),
        },
        cache: "no-store",
      },
    );

    const body: unknown = await backendResponse.json().catch(() => ({
      message: "Payroll operations could not be loaded.",
    }));

    return NextResponse.json(body, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      { message: "The payroll API is temporarily unavailable." },
      { status: 502 },
    );
  }
}
