import Image from "next/image";
import Link from "next/link";

import { ApiStatus } from "@/components/api-status";

export default function Home() {
  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between gap-4 border-b border-[var(--border)] pb-6">
          <Image
            src="/brand/build360-logo.png"
            alt="MPSqre Build360"
            width={192}
            height={128}
            priority
            className="h-16 w-auto object-contain"
          />
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-900">
            Foundation
          </span>
        </header>

        <section className="grid gap-8 py-12 lg:grid-cols-[1.5fr_1fr] lg:items-center">
          <div>
            <p className="mb-3 text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              Construction Operating System
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
              One controlled operating spine for construction delivery.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--muted)]">
              Identity, tenancy, versioned configuration, workflow approvals, entitlements,
              governed files, audit search, and outbox controls are active.
            </p>
            <Link
              className="mt-7 inline-flex rounded-lg bg-[var(--brand)] px-5 py-3 font-semibold text-white"
              href="/platform"
            >
              Open platform
            </Link>
          </div>

          <ApiStatus />
        </section>
      </div>
    </main>
  );
}
