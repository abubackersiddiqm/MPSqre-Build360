import { NextRequest, NextResponse } from "next/server";
import { accessToken, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ path: string[] }> };
export async function GET(request: NextRequest, context: RouteContext) {
  const [token, companyPublicId, params] = await Promise.all([accessToken(), selectedCompany(), context.params]);
  if (!token || !companyPublicId) return NextResponse.json({ message: "Authentication and company selection are required." }, { status: 401 });
  const joined = params.path.map(encodeURIComponent).join("/");
  const backendPath = joined.startsWith("projects/") ? `/${joined}` : `/projects/${joined}`;
  const response = await fetch(backendUrl(`${backendPath}${request.nextUrl.search}`), { headers: { Accept: "application/json", Authorization: `Bearer ${token}`, "X-Company-Id": companyPublicId, "X-Request-Id": crypto.randomUUID() }, cache: "no-store" }).catch(() => null);
  if (!response) return NextResponse.json({ message: "Project360 backend is unavailable." }, { status: 503 });
  return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" } });
}
