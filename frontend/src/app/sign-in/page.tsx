import type { Metadata } from "next";
import type { CSSProperties } from "react";

import { domainBrandForCurrentHost } from "@/lib/branding/domain-brand";
import { SignInForm } from "./sign-in-form";

type Props = { searchParams: Promise<{ next?: string | string[] }> };

export async function generateMetadata(): Promise<Metadata> {
  const mapped = await domainBrandForCurrentHost();
  const productName = mapped?.branding.product_name || "MPSqre Build360";
  const favicon = mapped?.branding.favicon_url;
  return {
    applicationName: productName,
    title: { absolute: `Sign in · ${productName}` },
    icons: favicon ? { icon: [{ url: favicon }] } : undefined,
  };
}

export default async function SignInPage({ searchParams }: Readonly<Props>) {
  const params = await searchParams;
  const requested = typeof params.next === "string" ? params.next : "/select-company";
  const nextPath = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/select-company";
  const mapped = await domainBrandForCurrentHost();
  const branding = mapped?.branding;
  const primaryColor = branding?.primary_color ?? "#174d3c";
  const style = {
    "--brand": primaryColor,
    "--brand-strong": branding?.accent_color ?? "#0f382b",
    "--brand-soft": /^#[0-9a-f]{6}$/i.test(primaryColor) ? `${primaryColor}14` : "#e8f2ee",
  } as CSSProperties;

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-5 py-10" style={style}>
      {branding?.login_background_url ? (
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-cover bg-center opacity-20"
          style={{ backgroundImage: `url(${branding.login_background_url})` }}
        />
      ) : null}
      <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_80%_10%,var(--brand-soft),transparent_35rem)]" />
      <section className="relative w-full max-w-md rounded-[28px] border border-[var(--border)] bg-white/95 p-7 shadow-xl backdrop-blur">
        {branding?.logo_url ? (
          <div
            aria-label={`${branding.product_name} logo`}
            className="mb-5 h-12 w-40 bg-contain bg-left bg-no-repeat"
            role="img"
            style={{ backgroundImage: `url(${branding.logo_url})` }}
          />
        ) : null}
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--brand)]">{branding?.product_name || "MPSqre Build360"}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-2 leading-6 text-[var(--muted)]">{branding?.tagline || "Access is limited to active company memberships and registered devices."}</p>
        <SignInForm nextPath={nextPath} />
        {branding?.powered_by_build360 === false ? null : (
          <p className="mt-6 text-center text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Powered by MPSqre Build360</p>
        )}
      </section>
    </main>
  );
}
