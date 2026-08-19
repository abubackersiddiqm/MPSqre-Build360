"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type AcceptanceResponse = {
  company?: { public_id: string; code: string; display_name: string };
  message?: string;
  detail?: string;
};

export function PortalAcceptanceForm({ initialInvitation, initialToken }: Readonly<{ initialInvitation: string; initialToken: string }>) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/portal/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        initialInvitation
          ? { invitation_public_id: initialInvitation }
          : { token: form.get("token") },
      ),
    }).catch(() => null);
    const body = (await response?.json().catch(() => ({}))) as AcceptanceResponse;
    if (!response?.ok || !body.company?.public_id) {
      setSubmitting(false);
      setError(body.message ?? body.detail ?? "The invitation could not be accepted.");
      return;
    }
    const selection = await fetch("/api/auth/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_public_id: body.company.public_id }),
    }).catch(() => null);
    setSubmitting(false);
    if (!selection?.ok) {
      setError("The invitation was accepted, but company selection failed. Open Choose company and select it manually.");
      return;
    }
    router.replace("/portal");
    router.refresh();
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={submit}>
      {initialInvitation ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <p className="font-semibold">Secure invitation link detected</p>
          <p className="mt-1 text-xs">
            Your signed-in email must exactly match the invited email. No bearer invitation token is stored in the communication message.
          </p>
        </div>
      ) : (
        <div>
          <label className="block text-sm font-medium" htmlFor="token">
            Invitation token
          </label>
          <textarea
            className="mt-2 min-h-28 w-full rounded-xl border border-[var(--border)] p-3 font-mono text-xs"
            defaultValue={initialToken}
            id="token"
            name="token"
            required
          />
        </div>
      )}
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
      <button
        className="w-full rounded-xl bg-[var(--brand)] px-4 py-3 font-semibold text-white disabled:opacity-60"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Accepting invitation…" : "Accept invitation"}
      </button>
    </form>
  );
}
