import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Offline" };

export default function OfflinePage() {
  return (
    <main className="grid min-h-screen place-items-center px-6 py-12">
      <section className="w-full max-w-lg rounded-3xl border border-[var(--border)] bg-white p-8 text-center shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--brand)]">
          MPSqre Build360
        </p>
        <h1 className="mt-4 text-3xl font-semibold">You are offline</h1>
        <p className="mt-4 leading-7 text-[var(--muted)]">
          Build360 protects live tenant data and does not cache authenticated business pages.
          Reconnect to continue. Approved field workflows use their own controlled synchronization process.
        </p>
        <Link
          className="mt-7 inline-flex rounded-xl bg-[var(--brand)] px-5 py-3 font-semibold text-white"
          href="/platform"
        >
          Retry connection
        </Link>
      </section>
    </main>
  );
}
