import { NextRequest, NextResponse } from "next/server";
import { accessToken, backendUrl, selectedCompany } from "@/lib/auth/server-session";

type RouteContext = { params: Promise<{ slot: string }> };
type Brand = {
  logo_file_public_id?: string | null;
  compact_logo_file_public_id?: string | null;
  favicon_file_public_id?: string | null;
  login_background_file_public_id?: string | null;
};

const fileKey: Record<string, keyof Brand> = {
  logo: "logo_file_public_id",
  compact_logo: "compact_logo_file_public_id",
  favicon: "favicon_file_public_id",
  login_background: "login_background_file_public_id",
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { slot } = await context.params;
  if (!fileKey[slot]) return new NextResponse(null, { status: 404 });
  const rawHost = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? "";
  const host = rawHost.split(",", 1)[0]?.trim().split(":", 1)[0]?.toLowerCase() ?? "";

  // Public custom/platform-domain path: host resolves the tenant without granting tenant membership.
  if (host && host !== "localhost" && host !== "127.0.0.1") {
    const response = await fetch(
      backendUrl(`/companies/domain/asset?host=${encodeURIComponent(host)}&slot=${encodeURIComponent(slot)}`),
      { cache: "no-store" },
    ).catch(() => null);
    if (!response?.ok) return new NextResponse(null, { status: response?.status ?? 503 });
    const body = (await response.json()) as { download_url: string; cache_seconds?: number };
    const redirect = NextResponse.redirect(body.download_url, 307);
    redirect.headers.set("Cache-Control", `public, max-age=${body.cache_seconds ?? 120}`);
    return redirect;
  }

  // Local UAT fallback: only an authenticated selected-company session may resolve the asset.
  const [token, companyPublicId] = await Promise.all([accessToken(), selectedCompany()]);
  if (!token || !companyPublicId) return new NextResponse(null, { status: 404 });
  const headers = new Headers({ Authorization: `Bearer ${token}`, "X-Company-Id": companyPublicId, Accept: "application/json", "X-Request-Id": crypto.randomUUID() });
  const brandResponse = await fetch(backendUrl("/companies/current/branding"), { headers, cache: "no-store" }).catch(() => null);
  if (!brandResponse?.ok) return new NextResponse(null, { status: 404 });
  const brand = (await brandResponse.json()) as Brand;
  const fileId = brand[fileKey[slot]];
  if (!fileId) return new NextResponse(null, { status: 404 });
  const download = await fetch(backendUrl(`/files/${encodeURIComponent(fileId)}/download`), { headers, cache: "no-store" }).catch(() => null);
  if (!download?.ok) return new NextResponse(null, { status: 404 });
  const body = (await download.json()) as { download_url: string };
  return NextResponse.redirect(body.download_url, 307);
}
