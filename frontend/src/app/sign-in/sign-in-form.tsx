"use client";

import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type SignInResponse = {
  message?: string;
  company_selected?: boolean;
  membership_count?: number;
};

export function SignInForm({ nextPath = "/select-company" }: Readonly<{ nextPath?: string }>) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        device_id: crypto.randomUUID(),
        device_name: navigator.userAgent.slice(0, 200),
      }),
    }).catch(() => null);
    setSubmitting(false);
    if (!response?.ok) {
      const body = (await response?.json().catch(() => null)) as SignInResponse | null;
      setError(
        body?.message ||
          "Sign in could not be completed. Confirm the API is running and try again.",
      );
      return;
    }
    const body = (await response.json().catch(() => ({}))) as SignInResponse;
    const requested: Route =
      nextPath.startsWith("/") && !nextPath.startsWith("//")
        ? (nextPath as Route)
        : "/";
    const destination: Route = body.company_selected
      ? requested === "/select-company"
        ? "/"
        : requested
      : "/select-company";
    router.replace(destination);
    router.refresh();
  }

  return (
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <div>
        <label className="block text-sm font-medium" htmlFor="email">
          Email address
        </label>
        <input
          autoComplete="username"
          className="mt-2 w-full rounded-lg border border-[var(--border)] px-3 py-3"
          id="email"
          name="email"
          required
          type="email"
        />
      </div>
      <div>
        <label className="block text-sm font-medium" htmlFor="password">
          Password
        </label>
        <input
          autoComplete="current-password"
          className="mt-2 w-full rounded-lg border border-[var(--border)] px-3 py-3"
          id="password"
          name="password"
          required
          type="password"
        />
      </div>
      {error ? (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      <button
        className="w-full rounded-lg bg-[var(--brand)] px-4 py-3 font-semibold text-white hover:bg-[var(--brand-strong)] disabled:opacity-60"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-center text-sm">
        <Link className="font-semibold text-[var(--brand)]" href="/forgot-password">Forgot password?</Link>
      </p>
    </form>
  );
}
