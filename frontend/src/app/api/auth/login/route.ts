import { NextRequest, NextResponse } from "next/server";

import {
  assertSameOrigin,
  backendUrl,
  setCompanyCookie,
  setTokenCookies,
  type TokenResponse,
} from "@/lib/auth/server-session";

type BackendErrorEnvelope = {
  code?: string;
  message?: string;
  request_id?: string;
};

type DomainResolution = { company: { public_id: string } };
type MeResponse = { memberships?: Array<{ company: { public_id: string } }> };

export async function POST(request: NextRequest) {
  if (!assertSameOrigin(request)) {
    return NextResponse.json(
      { code: "AUTH-ORIGIN-REJECTED", message: "Invalid request origin." },
      { status: 403 },
    );
  }

  const body: unknown = await request.json().catch(() => null);
  let backendResponse: Response;
  try {
    backendResponse = await fetch(backendUrl("/auth/token"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (error) {
    console.error("Build360 authentication backend is unavailable", {
      error: error instanceof Error ? error.message : "Unknown backend connection error",
    });
    return NextResponse.json(
      {
        code: "AUTH-BACKEND-UNAVAILABLE",
        message:
          "Authentication service is unavailable. Confirm the Django API is running on port 8000.",
      },
      { status: 503 },
    );
  }

  if (!backendResponse.ok) {
    const backendError = (await backendResponse.json().catch(() => ({}))) as
      BackendErrorEnvelope;
    const message =
      backendResponse.status === 401
        ? "Email or password is incorrect."
        : backendResponse.status === 429
          ? "Too many sign-in attempts. Wait briefly and try again."
          : backendError.message || "Sign in could not be completed.";
    return NextResponse.json(
      {
        code: backendError.code || `AUTH-${backendResponse.status}`,
        message,
        request_id:
          backendError.request_id || backendResponse.headers.get("X-Request-Id"),
      },
      { status: backendResponse.status },
    );
  }

  const tokens = (await backendResponse.json()) as TokenResponse;

  // A mapped subdomain/custom domain may preselect its company, but membership is
  // still authoritative. A host mapping never grants tenant access by itself.
  let mappedCompanyPublicId = "";
  const host = request.nextUrl.hostname.toLowerCase();
  try {
    const domainResponse = await fetch(backendUrl(`/companies/domain/resolve?host=${encodeURIComponent(host)}`), { cache: "no-store" });
    if (domainResponse.ok) {
      const domain = (await domainResponse.json()) as DomainResolution;
      mappedCompanyPublicId = domain.company.public_id;
    }
  } catch {
    // Domain-aware login is optional; normal multi-company selection remains available.
  }

  let selectedCompanyPublicId = "";
  let membershipCount = 0;
  try {
    const meResponse = await fetch(backendUrl("/auth/me"), {
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
        "X-Request-Id": crypto.randomUUID(),
      },
      cache: "no-store",
    });
    if (meResponse.ok) {
      const me = (await meResponse.json()) as MeResponse;
      const memberships = me.memberships ?? [];
      membershipCount = memberships.length;
      if (
        mappedCompanyPublicId &&
        memberships.some((membership) => membership.company.public_id === mappedCompanyPublicId)
      ) {
        selectedCompanyPublicId = mappedCompanyPublicId;
      } else if (memberships.length === 1) {
        selectedCompanyPublicId = memberships[0]?.company.public_id ?? "";
      }
    }
  } catch {
    // Membership discovery is best-effort. Multi-company selection remains the safe fallback.
  }

  const response = NextResponse.json({
    session_public_id: tokens.session_public_id,
    access_expires_at: tokens.access_expires_at,
    company_selected: Boolean(selectedCompanyPublicId),
    membership_count: membershipCount,
  });
  setTokenCookies(response, tokens);
  if (selectedCompanyPublicId) setCompanyCookie(response, selectedCompanyPublicId);
  return response;
}
