"use client";

import { useEffect, useState } from "react";

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
};

export function CompanySelector() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then(async (meResponse) => {
        if (!meResponse.ok) throw new Error("unauthorized");
        const data = (await meResponse.json()) as {
          memberships: Array<{ company: Company }>;
        };
        const available = data.memberships.map((membership) => membership.company);
        if (available.length === 1) {
          const response = await fetch("/api/auth/company", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ company_public_id: available[0]?.public_id }),
          });
          if (!response.ok) throw new Error("company-unavailable");
          window.location.replace("/");
          return;
        }
        setCompanies(available);
      })
      .catch(() => setError("Your authorized workspaces could not be loaded. Please sign in again."))
      .finally(() => setLoaded(true));
  }, []);

  async function selectCompany(companyPublicId: string) {
    setError("");
    const response = await fetch("/api/auth/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_public_id: companyPublicId }),
    });
    if (!response.ok) {
      setError("This company is no longer available to your account.");
      return;
    }
    window.location.assign("/");
  }

  return (
    <section className="mt-8">
      {error ? (
        <p className="mb-4 rounded-lg bg-red-50 p-4 text-red-800" role="alert">
          {error}
        </p>
      ) : null}
      <ul className="grid gap-4 sm:grid-cols-2">
        {companies.map((company) => (
          <li key={company.public_id}>
            <button
              className="w-full rounded-xl border border-[var(--border)] bg-white p-5 text-left shadow-sm hover:border-[var(--brand)]"
              onClick={() => selectCompany(company.public_id)}
              type="button"
            >
              <span className="block font-semibold">{company.display_name}</span>
              <span className="mt-1 block text-sm text-[var(--muted)]">
                {company.code} · {company.timezone}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {loaded && !error && companies.length === 0 ? (
        <p className="rounded-lg border border-[var(--border)] bg-white p-5 text-[var(--muted)]">
          No active company membership is assigned to this account. Ask a company administrator to
          issue an invitation.
        </p>
      ) : null}
      {!loaded && !error ? (
        <p className="text-[var(--muted)]" aria-live="polite">
          Loading authorized workspaces…
        </p>
      ) : null}
    </section>
  );
}
