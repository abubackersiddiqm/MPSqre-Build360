"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { visibleWorkspaces } from "@/lib/navigation/workspaces";

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
};

export function WorkspaceCatalog({
  company,
  permissions,
  platformOperator,
}: Readonly<{
  company: Company;
  permissions: string[];
  platformOperator: boolean;
}>) {
  const [query, setQuery] = useState("");

  const workspaces = useMemo(() => {
    const all = visibleWorkspaces({ permissions, platformOperator });
    const normalized = query.trim().toLowerCase();
    return normalized
      ? all.filter((workspace) =>
          `${workspace.title} ${workspace.description}`.toLowerCase().includes(normalized),
        )
      : all;
  }, [permissions, platformOperator, query]);

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
            Unified workspace launcher
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            {company.display_name}
          </h1>
          <p className="mt-3 max-w-2xl leading-7 text-[var(--muted)]">
            Only modules allowed by your effective permissions and platform role are shown.
          </p>
        </header>

        <div className="py-6">
          <label className="sr-only" htmlFor="workspace-catalog-search">
            Filter workspaces
          </label>
          <input
            className="w-full max-w-xl rounded-xl border border-[var(--border)] bg-white px-4 py-3"
            id="workspace-catalog-search"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by workspace or responsibility"
            value={query}
          />
        </div>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {workspaces.map((workspace) => (
            <Link
              className="group rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-800 hover:shadow-md"
              href={workspace.href}
              key={workspace.key}
            >
              <div className="flex items-start gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-emerald-950 text-xs font-bold text-white">
                  {workspace.badge}
                </span>
                <div>
                  <h2 className="font-semibold group-hover:text-emerald-950">
                    {workspace.title}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                    {workspace.description}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </section>

        {workspaces.length === 0 ? (
          <p className="rounded-2xl border border-[var(--border)] bg-white p-6 text-[var(--muted)]">
            No authorized workspace matches this filter.
          </p>
        ) : null}
      </div>
    </main>
  );
}
