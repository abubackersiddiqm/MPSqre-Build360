"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useState, type CSSProperties } from "react";

import styles from "./invitation-acceptance.module.css";

type Preview = {
  valid: boolean;
  company_name: string;
  invitee_name: string;
  expires_at: string;
  branding: {
    product_name: string;
    tagline: string;
    primary_color: string;
    powered_by_build360: boolean;
    white_label_enabled: boolean;
  };
};

export function InvitationAcceptanceClient() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    void fetch(`/api/platform/access-control/invitations/preview?token=${encodeURIComponent(token)}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Invitation is invalid or has expired.");
        return (await response.json()) as Preview;
      })
      .then((payload) => {
        if (active) setPreview(payload);
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : "Invitation could not be opened.");
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") || "");
    const confirm = String(form.get("confirm") || "");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    const response = await fetch("/api/platform/access-control/invitations/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    }).catch(() => null);
    setBusy(false);
    if (!response?.ok) {
      const payload = (await response?.json().catch(() => ({}))) as { message?: string; detail?: string };
      setError(payload?.message || payload?.detail || "Invitation acceptance failed.");
      return;
    }
    setSuccess(true);
  }

  const productName = preview?.branding.product_name || "MPSqre Build360";
  const primaryColor = preview?.branding.primary_color || "#00624c";
  const brandStyle = { "--invite-brand": primaryColor } as CSSProperties;

  return (
    <main className={styles.page} style={brandStyle}>
      <section className={styles.card}>
        <p className={styles.kicker}>{productName}</p>
        <h1>Activate your account</h1>
        <p className={styles.copy}>
          {preview
            ? `${preview.invitee_name || "You"}, activate your access to ${preview.company_name}.`
            : "Accept your company invitation and create a secure password."}
        </p>
        {preview?.branding.tagline ? <p className={styles.tagline}>{preview.branding.tagline}</p> : null}
        {!token ? (
          <p className={styles.error}>The invitation token is missing from this link.</p>
        ) : success ? (
          <>
            <p className={styles.success}>Your account and company membership are active.</p>
            <Link className={styles.link} href="/sign-in">Continue to sign in</Link>
          </>
        ) : (
          <form onSubmit={submit}>
            <div className={styles.field}>
              <label htmlFor="password">Create password</label>
              <input id="password" name="password" type="password" minLength={12} required autoComplete="new-password" />
            </div>
            <div className={styles.field}>
              <label htmlFor="confirm">Confirm password</label>
              <input id="confirm" name="confirm" type="password" minLength={12} required autoComplete="new-password" />
            </div>
            <p className={styles.copy}>
              New accounts require at least 12 characters with upper case, lower case and a number. Existing users must enter their current Build360 account password.
            </p>
            {error ? <p className={styles.error}>{error}</p> : null}
            <button className={styles.button} disabled={busy || (!!token && !preview && !error)} type="submit">
              {busy ? "Activating…" : "Accept invitation"}
            </button>
          </form>
        )}
        {preview?.branding.powered_by_build360 === false ? null : <p className={styles.powered}>Powered by MPSqre Build360</p>}
      </section>
    </main>
  );
}
