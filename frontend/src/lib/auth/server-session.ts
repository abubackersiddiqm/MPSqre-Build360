import "server-only";

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { joinBackendUrl, resolveBackendBaseUrl } from "./backend-url";

const securePrefix = process.env.NODE_ENV === "production" ? "__Host-" : "";
const accessCookie = `${securePrefix}build360-access`;
const refreshCookie = `${securePrefix}build360-refresh`;
const companyCookie = `${securePrefix}build360-company`;
const platformAccessCookie = `${securePrefix}build360-platform-access`;
const platformRefreshCookie = `${securePrefix}build360-platform-refresh`;

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  access_expires_at: string;
  refresh_expires_at: string;
  session_public_id: string;
};

function secureCookie(expires: Date) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict" as const,
    path: "/",
    expires,
  };
}

export function assertSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    return false;
  }
  try {
    return new URL(origin).host === request.nextUrl.host;
  } catch {
    return false;
  }
}

export function setTokenCookies(response: NextResponse, tokens: TokenResponse): void {
  response.cookies.set(
    accessCookie,
    tokens.access_token,
    secureCookie(new Date(tokens.access_expires_at)),
  );
  response.cookies.set(
    refreshCookie,
    tokens.refresh_token,
    secureCookie(new Date(tokens.refresh_expires_at)),
  );
}

export function setPlatformTokenCookies(response: NextResponse, tokens: TokenResponse): void {
  response.cookies.set(
    platformAccessCookie,
    tokens.access_token,
    secureCookie(new Date(tokens.access_expires_at)),
  );
  response.cookies.set(
    platformRefreshCookie,
    tokens.refresh_token,
    secureCookie(new Date(tokens.refresh_expires_at)),
  );
}

export function clearSessionCookies(response: NextResponse): void {
  for (const name of [accessCookie, refreshCookie, companyCookie]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/",
      maxAge: 0,
    });
  }
}

export function clearPlatformSessionCookies(response: NextResponse): void {
  for (const name of [platformAccessCookie, platformRefreshCookie]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/",
      maxAge: 0,
    });
  }
}

export async function accessToken(): Promise<string | undefined> {
  return (await cookies()).get(accessCookie)?.value;
}

export async function refreshToken(): Promise<string | undefined> {
  return (await cookies()).get(refreshCookie)?.value;
}

export async function platformAccessToken(): Promise<string | undefined> {
  return (await cookies()).get(platformAccessCookie)?.value;
}

export async function platformRefreshToken(): Promise<string | undefined> {
  return (await cookies()).get(platformRefreshCookie)?.value;
}

export async function selectedCompany(): Promise<string | undefined> {
  return (await cookies()).get(companyCookie)?.value;
}

export function setCompanyCookie(response: NextResponse, companyPublicId: string): void {
  response.cookies.set(companyCookie, companyPublicId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
}

export function backendUrl(path: string): string {
  const baseUrl = resolveBackendBaseUrl(
    process.env.INTERNAL_API_BASE_URL,
    process.env.NODE_ENV,
  );
  return joinBackendUrl(baseUrl, path);
}
