import { NextRequest, NextResponse } from "next/server";

import { accessToken, assertSameOrigin, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type Context = { params: Promise<{ path: string[] }> };
type BackendError = { message?: string; detail?: string; code?: string; request_id?: string };

async function proxy(request: NextRequest, context: Context, method: "GET" | "POST") {
  if (method !== "GET" && !assertSameOrigin(request)) {
    return NextResponse.json({ code: "PORTAL-ORIGIN-REJECTED", message: "Invalid request origin." }, { status: 403 });
  }
  const [token, tenant, params] = await Promise.all([accessToken(), selectedCompany(), context.params]);
  if (!token || !tenant) {
    return NextResponse.json({ code: "PORTAL-AUTH-REQUIRED", message: "Authenticated company context required." }, { status: 401 });
  }
  const suffix = params.path.map(encodeURIComponent).join("/");
  const query = request.nextUrl.search;
  const body = method === "POST" ? await request.text() : undefined;
  let response: Response;
  try {
    response = await fetch(backendUrl(`/portal/${suffix}${query}`), {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": request.headers.get("content-type") ?? "application/json",
        "X-Company-Id": tenant,
        "X-Request-Id": crypto.randomUUID(),
      },
      body,
      cache: "no-store",
    });
  } catch (error) {
    console.error("Build360 portal backend unavailable", { error: error instanceof Error ? error.message : "Unknown error" });
    return NextResponse.json({ code: "PORTAL-BACKEND-UNAVAILABLE", message: "Portal service is unavailable." }, { status: 503 });
  }
  const responseBody = (await response.json().catch(() => ({}))) as BackendError;
  return NextResponse.json(responseBody, { status: response.status });
}

export async function GET(request: NextRequest, context: Context) {
  return proxy(request, context, "GET");
}

export async function POST(request: NextRequest, context: Context) {
  return proxy(request, context, "POST");
}
