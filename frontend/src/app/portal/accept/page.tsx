import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { accessToken } from "@/lib/auth/server-session";
import { PortalAcceptanceForm } from "./accept-form";

export const metadata: Metadata = { title: "Accept portal invitation" };

type Props = { searchParams: Promise<{ token?: string | string[]; invitation?: string | string[] }> };

export default async function PortalAcceptancePage({ searchParams }: Readonly<Props>) {
  const params = await searchParams;
  const token = typeof params.token === "string" ? params.token : "";
  const invitation = typeof params.invitation === "string" ? params.invitation : "";
  if (!(await accessToken())) {
    const destination = invitation
      ? `/portal/accept?invitation=${encodeURIComponent(invitation)}`
      : token
        ? `/portal/accept?token=${encodeURIComponent(token)}`
        : "/portal/accept";
    redirect(`/sign-in?next=${encodeURIComponent(destination)}`);
  }
  return (
    <main className="grid min-h-screen place-items-center px-5 py-10">
      <section className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-white p-7 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--brand)]">
          MPSqre Build360 · External access
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">Accept portal invitation</h1>
        <p className="mt-2 leading-6 text-[var(--muted)]">
          Access is granted only after the invitation, signed-in email and company scope are validated by the server.
        </p>
        <PortalAcceptanceForm initialInvitation={invitation} initialToken={token} />
        <Link className="mt-5 inline-block text-sm font-semibold text-[var(--brand)] underline" href="/select-company">
          Choose an existing company instead
        </Link>
      </section>
    </main>
  );
}
