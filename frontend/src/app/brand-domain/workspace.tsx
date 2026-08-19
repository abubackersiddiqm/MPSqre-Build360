"use client";

import { FormEvent, useMemo, useState } from "react";

export type Company = { public_id: string; code: string; display_name: string; legal_name?: string; primary_domain?: string | null };
export type BrandProfile = {
  public_id: string; product_name: string; tagline: string; logo_url: string; compact_logo_url: string; favicon_url: string;
  login_background_url: string; logo_file_public_id?: string | null; compact_logo_file_public_id?: string | null;
  favicon_file_public_id?: string | null; login_background_file_public_id?: string | null;
  primary_color: string; accent_color: string; sidebar_style: string; sender_name: string;
  support_email: string; document_footer: string; powered_by_build360: boolean; version: number;
};
export type TenantDomain = {
  public_id: string; domain: string; domain_type: string; status: string; is_primary: boolean; verification_record_name: string;
  verification_record_value: string; expected_cname: string; verified_at: string | null; ssl_status: string; activated_at: string | null; version: number;
};
export type DomainList = { items: TenantDomain[]; platform_domain_suffix: string; custom_domain_cname_target: string };
export type EmailDeliveryProfile = {
  public_id: string; delivery_mode: "PLATFORM" | "TENANT_SMTP"; smtp_host: string; smtp_port: number; smtp_username: string;
  password_configured: boolean; smtp_use_tls: boolean; smtp_use_ssl: boolean; from_email: string; reply_to_email: string;
  status: "DISABLED" | "PENDING" | "ACTIVE" | "FAILED"; effective_route: "PLATFORM" | "TENANT_SMTP";
  last_tested_at: string | null; verified_at: string | null; last_error_code: string; version: number; message?: string; test_sent_to?: string;
};
export type OnboardingSummary = {
  company: { code: string; display_name: string };
  completion_percent: number;
  steps: { code: string; label: string; done: boolean; optional?: boolean }[];
  domains: TenantDomain[];
};
export type BrandAssetCandidate = {
  file_public_id: string; purpose_code: string; original_name: string; content_type: string;
  upload_status: string; scan_status: string; created_at: string;
};

type Props = {
  company: Company; permissions: string[]; features: Record<string, boolean>; initialBranding: BrandProfile | null; initialDomains: DomainList;
  initialOnboarding: OnboardingSummary | null; initialAssets: BrandAssetCandidate[]; initialEmailDelivery: EmailDeliveryProfile | null;
};

type AssetSlot = "logo" | "compact_logo" | "favicon" | "login_background";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/brand-domain/${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  const body = (await response.json().catch(() => ({}))) as { message?: string; detail?: string; field_errors?: Record<string, string[]> };
  if (!response.ok) {
    const firstField = body.field_errors ? Object.values(body.field_errors).flat()[0] : undefined;
    throw new Error(firstField ?? body.message ?? body.detail ?? "Brand & domain request failed.");
  }
  return body as T;
}

async function sha256Hex(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, "0")).join("");
}

const field = "w-full rounded-xl border border-[var(--border)] bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[color:var(--brand-soft)]";
const purposeBySlot: Record<AssetSlot, string> = {
  logo: "tenant.brand.logo",
  compact_logo: "tenant.brand.compact_logo",
  favicon: "tenant.brand.favicon",
  login_background: "tenant.brand.login_background",
};
const slotLabels: Record<AssetSlot, string> = { logo: "Main logo", compact_logo: "Compact logo", favicon: "Favicon", login_background: "Login background" };

function Status({ value }: Readonly<{ value: string }>) {
  const active = value === "ACTIVE" || value === "CLEAN" || value === "FINALIZED";
  return <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${active ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800"}`}>{value.replaceAll("_", " ")}</span>;
}

export function BrandDomainWorkspace({ company, permissions, features, initialBranding, initialDomains, initialOnboarding, initialAssets, initialEmailDelivery }: Readonly<Props>) {
  const [branding, setBranding] = useState(initialBranding);
  const [domains, setDomains] = useState(initialDomains.items);
  const [onboarding, setOnboarding] = useState(initialOnboarding);
  const [assets, setAssets] = useState(initialAssets);
  const [emailDelivery, setEmailDelivery] = useState(initialEmailDelivery);
  const [emailBusy, setEmailBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [assetBusy, setAssetBusy] = useState<AssetSlot | null>(null);
  const canBrand = permissions.includes("tenant.branding.manage") && features["tenant.white_label"] === true;
  const canDomain = permissions.includes("tenant.domain.manage") && features["tenant.custom_domain"] === true;
  const canUpload = canBrand && permissions.includes("files.upload");
  const preview = branding ?? {
    public_id: "", product_name: company.display_name, tagline: "Construction Operating System", logo_url: "", compact_logo_url: "", favicon_url: "", login_background_url: "",
    primary_color: "#174D3C", accent_color: "#0F766E", sidebar_style: "LIGHT", sender_name: company.display_name, support_email: "", document_footer: "", powered_by_build360: true, version: 1,
  };
  const platformSuggestion = useMemo(() => initialDomains.platform_domain_suffix ? `${company.code.toLowerCase()}.${initialDomains.platform_domain_suffix}` : "", [company.code, initialDomains.platform_domain_suffix]);

  async function refreshOnboarding() {
    if (!permissions.includes("tenant.branding.read") || features["tenant.white_label"] !== true) return;
    const [next, candidates, mail] = await Promise.all([
      api<OnboardingSummary>("onboarding"),
      api<{ items: BrandAssetCandidate[] }>("branding/assets"),
      api<EmailDeliveryProfile>("email-delivery"),
    ]);
    setOnboarding(next); setAssets(candidates.items); setEmailDelivery(mail);
  }

  async function saveBrand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!branding) return;
    const form = new FormData(event.currentTarget); setBusy(true); setMessage("");
    try {
      const updated = await api<BrandProfile>("branding", { method: "PATCH", body: JSON.stringify({
        expected_version: branding.version,
        product_name: form.get("product_name"), tagline: form.get("tagline"), logo_url: form.get("logo_url"), compact_logo_url: form.get("compact_logo_url"),
        favicon_url: form.get("favicon_url"), login_background_url: form.get("login_background_url"), primary_color: form.get("primary_color"), accent_color: form.get("accent_color"),
        sidebar_style: form.get("sidebar_style"), sender_name: form.get("sender_name"), support_email: form.get("support_email"), document_footer: form.get("document_footer"),
        powered_by_build360: form.get("powered_by_build360") === "on",
      }) });
      setBranding(updated); setMessage("Brand identity saved."); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Brand update failed."); } finally { setBusy(false); }
  }

  async function uploadAsset(slot: AssetSlot, file: File | null) {
    if (!file || !branding) return;
    setAssetBusy(slot); setMessage("");
    try {
      if (!file.type.startsWith("image/")) throw new Error("Choose a PNG, JPEG or WebP image.");
      const checksum = await sha256Hex(file);
      const initiated = await fetch("/api/files/uploads", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ purpose_code: purposeBySlot[slot], data_class: "public_brand", original_name: file.name, content_type: file.type, size_bytes: file.size, sha256: checksum }),
      });
      const upload = await initiated.json() as { file_public_id?: string; version_public_id?: string; upload_url?: string; upload_headers?: Record<string, string>; message?: string; detail?: string };
      if (!initiated.ok || !upload.upload_url || !upload.version_public_id || !upload.file_public_id) throw new Error(upload.message ?? upload.detail ?? "Brand upload could not start.");
      const put = await fetch(upload.upload_url, { method: "PUT", headers: upload.upload_headers, body: file });
      if (!put.ok) throw new Error("Object storage upload failed.");
      const finalized = await fetch(`/api/files/uploads/${upload.version_public_id}/finalize`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (!finalized.ok) { const body = await finalized.json().catch(() => ({})) as { message?: string; detail?: string }; throw new Error(body.message ?? body.detail ?? "Brand upload finalization failed."); }
      try {
        const attached = await api<BrandProfile>("branding/assets/attach", { method: "POST", body: JSON.stringify({ expected_version: branding.version, slot, file_public_id: upload.file_public_id }) });
        setBranding(attached); setMessage(`${slotLabels[slot]} uploaded and activated.`);
      } catch (error) {
        setMessage(`${slotLabels[slot]} uploaded. ${error instanceof Error ? error.message : "Wait for the security scan, then activate it below."}`);
      }
      await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Brand asset upload failed."); } finally { setAssetBusy(null); }
  }

  async function attachAsset(slot: AssetSlot, filePublicId: string) {
    if (!branding) return; setAssetBusy(slot); setMessage("");
    try {
      const attached = await api<BrandProfile>("branding/assets/attach", { method: "POST", body: JSON.stringify({ expected_version: branding.version, slot, file_public_id: filePublicId }) });
      setBranding(attached); setMessage(`${slotLabels[slot]} activated.`); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Brand asset activation failed."); } finally { setAssetBusy(null); }
  }

  async function saveEmailDelivery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!emailDelivery) return;
    const form = new FormData(event.currentTarget); setEmailBusy(true); setMessage("");
    try {
      const updated = await api<EmailDeliveryProfile>("email-delivery", { method: "PATCH", body: JSON.stringify({
        expected_version: emailDelivery.version,
        delivery_mode: form.get("delivery_mode"),
        smtp_host: form.get("smtp_host"),
        smtp_port: Number(form.get("smtp_port") || 587),
        smtp_username: form.get("smtp_username"),
        smtp_password: form.get("smtp_password"),
        clear_password: form.get("clear_password") === "on",
        smtp_use_tls: form.get("smtp_use_tls") === "on",
        smtp_use_ssl: form.get("smtp_use_ssl") === "on",
        from_email: form.get("from_email"),
        reply_to_email: form.get("reply_to_email"),
      }) });
      setEmailDelivery(updated); setMessage("Company email delivery settings saved. Test the connection before it becomes active."); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Email delivery settings could not be saved."); } finally { setEmailBusy(false); }
  }

  async function testEmailDelivery() {
    if (!emailDelivery) return; setEmailBusy(true); setMessage("");
    try {
      const tested = await api<EmailDeliveryProfile>("email-delivery/test", { method: "POST", body: JSON.stringify({ expected_version: emailDelivery.version }) });
      setEmailDelivery(tested); setMessage(tested.message ?? `Company SMTP verified. Test email sent to ${tested.test_sent_to ?? "your account"}.`); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Company SMTP verification failed. Platform mail remains active."); await refreshOnboarding().catch(()=>undefined); } finally { setEmailBusy(false); }
  }

  async function addDomain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement); setBusy(true); setMessage("");
    try {
      const item = await api<TenantDomain>("domains", { method: "POST", body: JSON.stringify({ domain: form.get("domain"), domain_type: form.get("domain_type"), make_primary: form.get("make_primary") === "on" }) });
      setDomains((current) => [item, ...current.filter((value) => value.public_id !== item.public_id)]); setMessage(`${item.domain} registered.`); formElement.reset(); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Domain registration failed."); } finally { setBusy(false); }
  }

  async function makePrimary(item: TenantDomain) {
    setBusy(true); setMessage("");
    try {
      const updated = await api<TenantDomain>(`domains/${item.public_id}/primary`, { method: "POST", body: JSON.stringify({ expected_version: item.version }) });
      setDomains((current) => current.map((value) => value.public_id === updated.public_id ? updated : { ...value, is_primary: false })); setMessage(`${updated.domain} is now primary.`); await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Primary-domain update failed."); } finally { setBusy(false); }
  }

  async function checkDomain(item: TenantDomain) {
    setBusy(true); setMessage("");
    try {
      const result = await api<TenantDomain & { message?: string }>(`domains/${item.public_id}/verify`, { method: "POST", body: JSON.stringify({ expected_version: item.version }) });
      setDomains((current) => current.map((value) => value.public_id === result.public_id ? result : value));
      setMessage(result.message ?? (result.status === "ACTIVE" ? `${result.domain} is active.` : "DNS/TLS operator verification is still required."));
      await refreshOnboarding();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Domain verification check failed."); } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-[var(--background)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl space-y-6">
    <header className="overflow-hidden rounded-[30px] border border-[var(--border)] bg-white shadow-sm"><div className="grid gap-6 p-6 lg:grid-cols-[1.15fr_.85fr] lg:p-8"><div><p className="text-xs font-bold uppercase tracking-[.2em] text-[var(--brand)]">White-label onboarding</p><h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">Launch each company with its own identity, address and client-facing experience.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">Brand assets use Build360 governed file storage. Custom-domain DNS/TLS remains evidence-driven at the deployment edge.</p></div><div className="rounded-[24px] p-5 text-white" style={{background:`linear-gradient(135deg,${preview.primary_color},${preview.accent_color})`}}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-white/70">Tenant ready</p><p className="mt-2 text-5xl font-semibold">{onboarding?.completion_percent ?? 0}%</p></div>{preview.logo_url?<span aria-label="Company logo" className="h-14 w-36 rounded-xl bg-white/95 bg-contain bg-center bg-no-repeat" role="img" style={{backgroundImage:`url(${preview.logo_url})`}}/>:null}</div><p className="mt-5 text-lg font-semibold">{preview.product_name || company.display_name}</p><p className="text-sm text-white/70">{preview.tagline}</p></div></div>
      {onboarding?<div className="grid border-t border-[var(--border)] sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{onboarding.steps.map((step)=><div className="border-b border-[var(--border)] p-4 last:border-b-0 lg:border-b-0 lg:border-r" key={step.code}><div className="flex items-center gap-2"><span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${step.done?"bg-emerald-100 text-emerald-800":"bg-slate-100 text-slate-500"}`}>{step.done?"✓":"○"}</span><p className="text-xs font-semibold">{step.label}{step.optional?" · optional":""}</p></div></div>)}</div>:null}
    </header>
    {message?<div className="rounded-2xl border border-[var(--border)] bg-white px-5 py-4 text-sm font-medium shadow-sm">{message}</div>:null}

    <section className="grid gap-6 xl:grid-cols-[1.1fr_.9fr]">
      <div className="space-y-6">
        <article className="rounded-[26px] border border-[var(--border)] bg-white p-6 shadow-sm"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Governed brand assets</p><h2 className="mt-1 text-2xl font-semibold">Upload logo & login visuals</h2><p className="mt-2 text-sm text-[var(--muted)]">Assets activate only after the existing file security scan is CLEAN.</p></div><div className="mt-5 grid gap-4 sm:grid-cols-2">{(Object.keys(purposeBySlot) as AssetSlot[]).map((slot)=><label className="rounded-2xl border border-[var(--border)] p-4" key={slot}><p className="font-semibold">{slotLabels[slot]}</p><p className="mt-1 text-xs text-[var(--muted)]">{purposeBySlot[slot]}</p>{canUpload?<input accept="image/png,image/jpeg,image/webp" className="mt-4 block w-full text-xs" disabled={assetBusy!==null} onChange={(event)=>void uploadAsset(slot,event.target.files?.[0]??null)} type="file"/>:<p className="mt-4 text-xs text-amber-700">Brand manage + files.upload required.</p>}{assetBusy===slot?<p className="mt-2 text-xs font-semibold text-[var(--brand)]">Uploading…</p>:null}</label>)}</div>
          {assets.length?<div className="mt-5"><p className="text-xs font-bold uppercase tracking-[.14em] text-[var(--muted)]">Recent brand files</p><div className="mt-3 space-y-2">{assets.slice(0,8).map((asset)=>{const slot=(Object.entries(purposeBySlot).find(([,purpose])=>purpose===asset.purpose_code)?.[0]??"logo") as AssetSlot;return <div className="flex flex-wrap items-center gap-2 rounded-xl bg-slate-50 p-3" key={asset.file_public_id}><span className="min-w-0 flex-1 truncate text-xs font-semibold">{asset.original_name}</span><Status value={asset.upload_status}/><Status value={asset.scan_status}/>{canBrand&&asset.scan_status==="CLEAN"&&asset.upload_status==="FINALIZED"?<button className="rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-[10px] font-bold" disabled={assetBusy!==null} onClick={()=>void attachAsset(slot,asset.file_public_id)} type="button">Use as {slotLabels[slot]}</button>:null}</div>})}</div></div>:null}
        </article>

        <form className="rounded-[26px] border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={saveBrand}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Company identity</p><h2 className="mt-1 text-2xl font-semibold">Brand system</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">v{preview.version}</span></div><div className="mt-6 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-semibold">Product name<input className={`${field} mt-2`} defaultValue={preview.product_name} disabled={!canBrand} name="product_name"/></label><label className="text-sm font-semibold">Tagline<input className={`${field} mt-2`} defaultValue={preview.tagline} disabled={!canBrand} name="tagline"/></label>
          <label className="text-sm font-semibold sm:col-span-2">Fallback logo URL<input className={`${field} mt-2`} defaultValue={preview.logo_url.startsWith("/api/")?"":preview.logo_url} disabled={!canBrand} name="logo_url" type="url"/></label><label className="text-sm font-semibold">Fallback compact logo URL<input className={`${field} mt-2`} defaultValue={preview.compact_logo_url.startsWith("/api/")?"":preview.compact_logo_url} disabled={!canBrand} name="compact_logo_url" type="url"/></label><label className="text-sm font-semibold">Fallback favicon URL<input className={`${field} mt-2`} defaultValue={preview.favicon_url.startsWith("/api/")?"":preview.favicon_url} disabled={!canBrand} name="favicon_url" type="url"/></label>
          <label className="text-sm font-semibold">Primary colour<input className={`${field} mt-2 h-11`} defaultValue={preview.primary_color} disabled={!canBrand} name="primary_color" type="color"/></label><label className="text-sm font-semibold">Accent colour<input className={`${field} mt-2 h-11`} defaultValue={preview.accent_color} disabled={!canBrand} name="accent_color" type="color"/></label><label className="text-sm font-semibold">Sidebar style<select className={`${field} mt-2`} defaultValue={preview.sidebar_style} disabled={!canBrand} name="sidebar_style"><option value="LIGHT">Light</option><option value="DARK">Dark</option><option value="BRAND">Brand</option></select></label><label className="text-sm font-semibold">Support email<input className={`${field} mt-2`} defaultValue={preview.support_email} disabled={!canBrand} name="support_email" type="email"/></label><label className="text-sm font-semibold">Sender name<input className={`${field} mt-2`} defaultValue={preview.sender_name} disabled={!canBrand} name="sender_name"/></label><label className="text-sm font-semibold sm:col-span-2">Fallback login background URL<input className={`${field} mt-2`} defaultValue={preview.login_background_url.startsWith("/api/")?"":preview.login_background_url} disabled={!canBrand} name="login_background_url" type="url"/></label><label className="text-sm font-semibold sm:col-span-2">Document footer<textarea className={`${field} mt-2 min-h-24`} defaultValue={preview.document_footer} disabled={!canBrand} name="document_footer"/></label><label className="flex items-center gap-3 text-sm font-semibold sm:col-span-2"><input defaultChecked={preview.powered_by_build360} disabled={!canBrand} name="powered_by_build360" type="checkbox"/> Show “Powered by MPSqre Build360”</label></div>{canBrand?<button className="mt-6 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white" disabled={busy} type="submit">Save brand identity</button>:null}</form>
      </div>

      <div className="space-y-6">{emailDelivery && canBrand?<form className="rounded-[26px] border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={saveEmailDelivery}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">White-label email delivery</p><h2 className="mt-1 text-2xl font-semibold">Company mail server</h2><p className="mt-2 text-sm leading-6 text-[var(--muted)]">Use your company SMTP only after a successful test. Until then Build360 platform mail remains the transactional fallback.</p></div><div className="flex gap-2"><Status value={emailDelivery.status}/><Status value={emailDelivery.effective_route}/></div></div><div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold sm:col-span-2">Delivery route<select className={`${field} mt-2`} defaultValue={emailDelivery.delivery_mode} disabled={emailBusy} name="delivery_mode"><option value="PLATFORM">Use Build360 platform mail</option><option value="TENANT_SMTP">Use this company SMTP</option></select></label>
        <label className="text-sm font-semibold">SMTP host<input className={`${field} mt-2`} defaultValue={emailDelivery.smtp_host} disabled={emailBusy} name="smtp_host" placeholder="smtp.company.com"/></label><label className="text-sm font-semibold">Port<input className={`${field} mt-2`} defaultValue={emailDelivery.smtp_port} disabled={emailBusy} min={1} max={65535} name="smtp_port" type="number"/></label>
        <label className="text-sm font-semibold sm:col-span-2">Username<input className={`${field} mt-2`} autoComplete="off" defaultValue={emailDelivery.smtp_username} disabled={emailBusy} name="smtp_username"/></label>
        <label className="text-sm font-semibold sm:col-span-2">Password<input className={`${field} mt-2`} autoComplete="new-password" disabled={emailBusy} name="smtp_password" placeholder={emailDelivery.password_configured?"Password stored securely — leave blank to keep it":"Enter SMTP/app password"} type="password"/><span className="mt-1 block text-xs font-normal text-[var(--muted)]">The password is encrypted at rest and is never returned to the browser.</span>{emailDelivery.password_configured?<label className="mt-2 flex items-center gap-2 text-xs font-medium text-[var(--muted)]"><input disabled={emailBusy} name="clear_password" type="checkbox"/> Remove stored SMTP password</label>:null}</label>
        <label className="text-sm font-semibold">From email<input className={`${field} mt-2`} defaultValue={emailDelivery.from_email} disabled={emailBusy} name="from_email" placeholder="no-reply@company.com" type="email"/></label><label className="text-sm font-semibold">Reply-to email<input className={`${field} mt-2`} defaultValue={emailDelivery.reply_to_email} disabled={emailBusy} name="reply_to_email" type="email"/></label>
        <label className="flex items-center gap-3 text-sm font-semibold"><input defaultChecked={emailDelivery.smtp_use_tls} disabled={emailBusy} name="smtp_use_tls" type="checkbox"/> STARTTLS / TLS</label><label className="flex items-center gap-3 text-sm font-semibold"><input defaultChecked={emailDelivery.smtp_use_ssl} disabled={emailBusy} name="smtp_use_ssl" type="checkbox"/> Implicit SSL</label>
      </div>{emailDelivery.last_tested_at?<p className="mt-4 text-xs text-[var(--muted)]">Last tested: {new Date(emailDelivery.last_tested_at).toLocaleString()}{emailDelivery.last_error_code?` · ${emailDelivery.last_error_code}`:""}</p>:null}<div className="mt-5 grid gap-3 sm:grid-cols-2"><button className="rounded-xl border border-[var(--border)] bg-white px-4 py-3 text-sm font-semibold" disabled={emailBusy} type="submit">Save email settings</button><button className="rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60" disabled={emailBusy || emailDelivery.delivery_mode!=="TENANT_SMTP"} onClick={()=>void testEmailDelivery()} type="button">Test & activate</button></div></form>:null}{canDomain?<form className="rounded-[26px] border border-[var(--border)] bg-white p-6 shadow-sm" onSubmit={addDomain}><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Tenant domains</p><h2 className="mt-1 text-2xl font-semibold">Add company address</h2><p className="mt-2 text-sm leading-6 text-[var(--muted)]">Platform subdomains can activate immediately when your deployment owns the wildcard. Custom domains remain pending until DNS and TLS are externally verified.</p><div className="mt-5 space-y-3"><select className={field} defaultValue="PLATFORM_SUBDOMAIN" name="domain_type"><option value="PLATFORM_SUBDOMAIN">Build360 subdomain</option><option value="CUSTOM_DOMAIN">Custom company domain</option></select><input className={field} defaultValue={platformSuggestion} name="domain" placeholder="erp.company.com" required/><label className="flex items-center gap-3 text-sm font-semibold"><input name="make_primary" type="checkbox"/> Make primary when active</label><button className="w-full rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white" disabled={busy} type="submit">Register domain</button></div></form>:null}
        <article className="rounded-[26px] border border-[var(--border)] bg-white p-6 shadow-sm"><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--brand)]">Domain register</p><h2 className="mt-1 text-2xl font-semibold">Addresses & DNS proof</h2><div className="mt-5 space-y-4">{domains.length?domains.map((item)=><div className="rounded-2xl border border-[var(--border)] p-4" key={item.public_id}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{item.domain}</p><p className="mt-1 text-xs text-[var(--muted)]">{item.domain_type.replaceAll("_"," ")}{item.is_primary?" · PRIMARY":""}</p></div><div className="flex gap-2"><Status value={item.status}/><Status value={item.ssl_status}/></div></div>{item.domain_type==="CUSTOM_DOMAIN"&&item.status!=="ACTIVE"?<div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600"><p><strong>CNAME:</strong> {item.domain} → {item.expected_cname||initialDomains.custom_domain_cname_target||"deployment target"}</p><p className="mt-1 break-all"><strong>TXT:</strong> {item.verification_record_name} = {item.verification_record_value}</p><p className="mt-2 text-amber-800">Build360 does not fake DNS/TLS verification. Activate only after deployment evidence.</p>{canDomain?<button className="mt-3 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-[10px] font-bold" disabled={busy} onClick={()=>void checkDomain(item)} type="button">Check activation requirements</button>:null}</div>:null}{canDomain&&item.status==="ACTIVE"&&!item.is_primary?<button className="mt-4 rounded-lg border border-[var(--border)] px-3 py-2 text-xs font-semibold" disabled={busy} onClick={()=>void makePrimary(item)} type="button">Make primary</button>:null}</div>):<p className="text-sm text-[var(--muted)]">No tenant domains registered yet.</p>}</div></article>
      </div>
    </section>
  </div></main>;
}
