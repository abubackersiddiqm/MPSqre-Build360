"use client";

import { useEffect, useState } from "react";

type State = "checking" | "available" | "unavailable";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
export function ApiStatus() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl}/health/live`, {
      cache: "no-store",
      signal: controller.signal,
      credentials: "omit",
    })
      .then((response) => setState(response.ok ? "available" : "unavailable"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setState("unavailable");
        }
      });
    return () => controller.abort();
  }, []);

  const label = {
    checking: "Checking API",
    available: "API available",
    unavailable: "API unavailable",
  }[state];

  return (
    <section
      aria-live="polite"
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm"
    >
      <h2 className="text-lg font-semibold">Platform status</h2>
      <div className="mt-4 flex items-center gap-3">
        <span
          aria-hidden="true"
          className={`h-3 w-3 rounded-full ${
            state === "available"
              ? "bg-emerald-600"
              : state === "checking"
                ? "bg-amber-500"
                : "bg-red-600"
          }`}
        />
        <span>{label}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
        Readiness additionally validates PostgreSQL and Redis without exposing internal details.
      </p>
    </section>
  );
}
