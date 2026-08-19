import type { Metadata } from "next";

import { CompanySelector } from "./selector";

export const metadata: Metadata = {
  title: "Select company",
};

export default function SelectCompanyPage() {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Choose your company</h1>
      <p className="mt-2 text-[var(--muted)]">
        Your selection is validated against your active memberships on the server.
      </p>
      <CompanySelector />
    </main>
  );
}

