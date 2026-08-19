"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./super-admin.module.css";

type Company = {
  public_id: string;
  code: string;
  legal_name: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
  unit_system_code: string;
  is_active: boolean;
  membership_count: number;
  plan_code: string;
  onboarding_status_code: string;
  primary_admin: null | {
    email: string;
    display_name: string;
    status: "ACTIVE" | "INVITE_PENDING" | "EXPIRED" | "REVOKED" | "ACCEPTED" | "NOT_INVITED" | string;
    invitation_public_id: string | null;
    expires_at: string | null;
    accepted_at: string | null;
    delivery_status_code?: string;
    delivery_attempted_at?: string | null;
    delivery_error_code?: string;
    delivery_brand_name?: string;
  };
};

type Overview = {
  summary: {
    company_count: number;
    active_company_count: number;
    suspended_company_count: number;
    active_operator_count: number;
    pending_admin_invitation_count: number;
    membership_count: number;
  };
  companies: Company[];
  recent_invitations: Array<{
    public_id: string;
    company_name: string;
    email: string;
    display_name: string;
    invitation_type_code: string;
    expires_at: string;
    accepted_at: string | null;
    revoked_at: string | null;
  }>;
};

type CreateResult = {
  company: { public_id: string; code: string; display_name: string };
  invitation: { public_id: string; email: string; expires_at: string; acceptance_token?: string; acceptance_url?: string; delivery: { status: string; brand_name: string; error_code: string } };
};

type AdminInviteResult = { public_id: string; email: string; expires_at: string; acceptance_token?: string; acceptance_url?: string; delivery: { status: string; brand_name: string; error_code: string } };

type FeatureItem = {
  code: string;
  label: string;
  group: string;
  kind: "MODULE" | "ADD_ON" | string;
  description: string;
  enabled: boolean;
  configured_enabled: boolean;
  source: string;
  requires: string[];
  override: null | {
    public_id: string;
    enabled: boolean;
    reason_code: string;
    effective_from: string;
    set_by_public_id: string;
  };
};

type FeatureMatrix = {
  company: { public_id: string; code: string; display_name: string };
  subscription: { status: string; plan_code: string | null; plan_version: number | null };
  presets: Array<{ code: string; label: string; description: string }>;
  items: FeatureItem[];
  generated_at: string;
};

async function jsonRequest<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
  const response = await fetch(`/api/platform/access-control/${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (response.status === 401 && retry) {
    const refreshed = await fetch("/api/platform-auth/refresh", { method: "POST" }).catch(() => null);
    if (refreshed?.ok) return jsonRequest<T>(path, init, false);
    window.location.assign("/super-admin/sign-in");
    throw new Error("Platform session expired. Sign in again.");
  }
  const payload = (await response.json().catch(() => ({}))) as { message?: string; detail?: string };
  if (!response.ok) throw new Error(payload.message || payload.detail || "The request could not be completed.");
  return payload as T;
}

export function SuperAdminClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastActivationUrl, setLastActivationUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [matrix, setMatrix] = useState<FeatureMatrix | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [featureBusy, setFeatureBusy] = useState("");
  const [presetBusy, setPresetBusy] = useState(false);
  const [presetCode, setPresetCode] = useState("CRM_ONLY");
  const [reasonCode, setReasonCode] = useState("subscription-change");
  const [activeFeatureSection, setActiveFeatureSection] = useState("crm");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await jsonRequest<Overview>("platform/overview");
      setOverview(next);
      setSelectedCompanyId((current) => current || next.companies[0]?.public_id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Platform control plane unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMatrix = useCallback(async (companyId: string) => {
    if (!companyId) {
      setMatrix(null);
      return;
    }
    setMatrixLoading(true);
    setError("");
    try {
      const next = await jsonRequest<FeatureMatrix>(`platform/companies/${companyId}/feature-matrix`);
      setMatrix(next);
      setPresetCode((current) =>
        next.presets.some((item) => item.code === current)
          ? current
          : (next.presets[0]?.code ?? "CRM_ONLY"),
      );
    } catch (caught) {
      setMatrix(null);
      setError(caught instanceof Error ? caught.message : "SaaS feature matrix could not be loaded.");
    } finally {
      setMatrixLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void load();
    });
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const refresh = () => {
      void fetch("/api/platform-auth/refresh", { method: "POST" });
    };
    const timer = window.setInterval(refresh, 8 * 60 * 1000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted && selectedCompanyId) void loadMatrix(selectedCompanyId);
    });
    return () => controller.abort();
  }, [loadMatrix, selectedCompanyId]);

  const featureSections = useMemo(() => {
    const all = matrix?.items ?? [];
    const crmCore = all.find((item) => item.code === "crm.core") ?? null;
    const crmAddOns = all.filter((item) => item.code.startsWith("crm.") && item.code !== "crm.core");
    const businessModules = all.filter((item) => item.group === "Business modules" && item.code !== "crm.core");
    const operationsModules = all.filter((item) => item.group === "Operations modules");
    const tenantExperience = all.filter((item) => item.group === "Tenant experience");

    const knownCodes = new Set([
      ...(crmCore ? [crmCore.code] : []),
      ...crmAddOns.map((item) => item.code),
      ...businessModules.map((item) => item.code),
      ...operationsModules.map((item) => item.code),
      ...tenantExperience.map((item) => item.code),
    ]);
    const remainingGroups = new Map<string, FeatureItem[]>();
    for (const item of all) {
      if (knownCodes.has(item.code)) continue;
      remainingGroups.set(item.group, [...(remainingGroups.get(item.group) ?? []), item]);
    }

    return [
      {
        id: "crm",
        label: "CRM suite",
        description: "CRM core with its optional sales, communication and automation add-ons.",
        parent: crmCore,
        items: crmAddOns,
      },
      {
        id: "business",
        label: "Business modules",
        description: "Primary Build360 business capabilities purchased by the tenant.",
        parent: null,
        items: businessModules,
      },
      {
        id: "operations",
        label: "Operations modules",
        description: "Extended delivery, asset and enterprise operations capabilities.",
        parent: null,
        items: operationsModules,
      },
      {
        id: "tenant",
        label: "Tenant experience",
        description: "Branding, domain and external platform capabilities.",
        parent: null,
        items: tenantExperience,
      },
      ...Array.from(remainingGroups.entries()).map(([group, items], index) => ({
        id: `extra-${index}`,
        label: group,
        description: "Additional governed tenant capabilities.",
        parent: null,
        items,
      })),
    ].filter((section) => section.parent || section.items.length);
  }, [matrix]);

  const selectedFeatureSection = useMemo(
    () => featureSections.find((section) => section.id === activeFeatureSection) ?? featureSections[0] ?? null,
    [activeFeatureSection, featureSections],
  );

  useEffect(() => {
    const firstSection = featureSections[0];
    if (!firstSection) return;
    if (!featureSections.some((section) => section.id === activeFeatureSection)) {
      setActiveFeatureSection(firstSection.id);
    }
  }, [activeFeatureSection, featureSections]);

  const moduleSummary = useMemo(() => {
    const modules = matrix?.items.filter((item) => item.kind === "MODULE") ?? [];
    return { enabled: modules.filter((item) => item.enabled).length, total: modules.length };
  }, [matrix]);

  async function createCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setError("");
    setNotice("");
    const f = new FormData(formElement);
    try {
      const result = await jsonRequest<CreateResult>("platform/companies", {
        method: "POST",
        body: JSON.stringify({
          code: f.get("code"),
          legal_name: f.get("legal_name"),
          display_name: f.get("display_name"),
          locale: f.get("locale"),
          timezone: f.get("timezone"),
          currency: f.get("currency"),
          unit_system_code: f.get("unit_system_code"),
          fiscal_year_start_month: Number(f.get("fiscal_year_start_month")),
          plan_code: f.get("plan_code"),
          preset_code: f.get("preset_code"),
          admin_email: f.get("admin_email"),
          admin_display_name: f.get("admin_display_name"),
          admin_employee_number: f.get("admin_employee_number"),
        }),
      });
      setLastActivationUrl(result.invitation.acceptance_url || "");
      if (result.invitation.delivery.status === "SENT") {
        setNotice(`Company created. Administrator invitation email sent to ${result.invitation.email}.`);
      } else if (result.invitation.delivery.status === "LOCAL_PREVIEW") {
        setNotice("Company created. Administrator invitation is ready.");
      } else {
        setNotice(`Company created, but the administrator email could not be delivered${result.invitation.delivery.error_code ? ` (${result.invitation.delivery.error_code})` : ""}. Fix email delivery and use Resend activation email.`);
      }
      formElement.reset();
      await load();
      setSelectedCompanyId(result.company.public_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Company creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function regeneratePrimaryAdminInvite(company: Company) {
    if (company.primary_admin?.status === "ACTIVE") {
      setError("This Company Administrator is already active. Use the tenant sign-in Forgot password flow instead of another activation invitation.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    setLastActivationUrl("");
    try {
      const result = await jsonRequest<AdminInviteResult>(`platform/companies/${company.public_id}/primary-admin-invitation`, {
        method: "POST",
        body: JSON.stringify({ ttl_hours: 72 }),
      });
      setLastActivationUrl(result.acceptance_url || "");
      if (result.delivery.status === "SENT") {
        setNotice(`Fresh administrator activation email sent to ${result.email}. The previous pending invitation is now revoked.`);
      } else if (result.delivery.status === "LOCAL_PREVIEW") {
        setNotice(`Fresh administrator invitation prepared for ${result.email}.`);
      } else {
        setNotice(`A fresh invitation was created for ${result.email}, but email delivery failed${result.delivery.error_code ? ` (${result.delivery.error_code})` : ""}.`);
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Primary administrator invitation could not be regenerated.");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(company: Company) {
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`platform/companies/${company.public_id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          is_active: !company.is_active,
          reason_code: company.is_active ? "operator_suspension" : "operator_reactivation",
        }),
      });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Status update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleFeature(item: FeatureItem) {
    const reason = reasonCode.trim();
    if (!reason) {
      setError("Enter a reason code before changing a SaaS feature.");
      return;
    }
    if (!selectedCompanyId) return;
    setFeatureBusy(item.code);
    setError("");
    setNotice("");
    try {
      const next = await jsonRequest<FeatureMatrix>(`platform/companies/${selectedCompanyId}/feature-matrix`, {
        method: "PATCH",
        body: JSON.stringify({ feature_code: item.code, enabled: !item.configured_enabled, reason_code: reason }),
      });
      setMatrix(next);
      setNotice(`${item.label} ${item.configured_enabled ? "disabled" : "enabled"} for ${next.company.display_name}. Backend entitlement enforcement is effective immediately.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Feature update failed.");
    } finally {
      setFeatureBusy("");
    }
  }

  async function applyPreset() {
    const reason = reasonCode.trim();
    if (!selectedCompanyId || !reason) {
      setError("Select a company and enter a reason code before applying a package preset.");
      return;
    }
    const selected = matrix?.presets.find((item) => item.code === presetCode);
    if (!window.confirm(`Apply ${selected?.label ?? presetCode} to ${matrix?.company.display_name ?? "this company"}? This appends governed entitlement overrides.`)) return;
    setPresetBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await jsonRequest<FeatureMatrix>(`platform/companies/${selectedCompanyId}/feature-matrix`, {
        method: "POST",
        body: JSON.stringify({ preset_code: presetCode, reason_code: reason }),
      });
      setMatrix(next);
      setNotice(`${selected?.label ?? presetCode} applied to ${next.company.display_name}. Access and navigation were updated automatically.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Package preset could not be applied.");
    } finally {
      setPresetBusy(false);
    }
  }

  if (loading && !overview) {
    return <main className={styles.page}><div className={styles.loading}>Loading platform control plane…</div></main>;
  }
  if (!overview) {
    return <main className={styles.page}><section className={styles.panel}><p className={styles.kicker}>Platform operator access required</p><h1>Super administration is not enabled for this session.</h1><p className={styles.panelIntro}>{error || "Sign in with an authorized Platform Operator account."}</p><div className={styles.actions}><a className={styles.button} href="/super-admin/sign-in">Super Admin sign in</a></div></section></main>;
  }

  function openPackage(companyId: string) {
    setSelectedCompanyId(companyId);
    window.requestAnimationFrame(() => {
      document.getElementById("tenant-package-control")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  function renderFeatureRow(item: FeatureItem, nested = false) {
    return <article className={`${styles.featureRow} ${nested ? styles.featureChildRow : ""}`} key={item.code}>
      <div className={styles.featureRowMain}>
        <div className={styles.featureRowTitle}>
          <div>
            <p className={styles.featureCode}>{nested ? "ADD-ON" : item.kind} · {item.code}</p>
            <h4>{item.label}</h4>
          </div>
          <span className={`${styles.pill} ${item.enabled ? styles.pillActive : styles.pillDanger}`}>{item.enabled ? "ENABLED" : "DISABLED"}</span>
        </div>
        <p className={styles.featureDescription}>{item.description}</p>
        {item.requires.length ? <p className={styles.dependency}>Requires: {item.requires.join(", ")}</p> : null}
        <div className={styles.featureMeta}>
          <span>Configured: <strong>{item.configured_enabled ? "ON" : "OFF"}</strong></span>
          <span>Source: <strong>{item.source}</strong></span>
          {item.override ? <span>Override: <strong>{item.override.reason_code}</strong></span> : null}
        </div>
      </div>
      <button className={`${styles.button} ${item.configured_enabled ? styles.buttonDanger : styles.button}`} disabled={Boolean(featureBusy) || presetBusy} onClick={() => void toggleFeature(item)} type="button">
        {featureBusy === item.code ? "Applying…" : item.configured_enabled ? "Disable" : "Enable"}
      </button>
    </article>;
  }

  async function signOutPlatform() {
    await fetch("/api/platform-auth/logout", { method: "POST" }).catch(() => null);
    window.location.assign("/super-admin/sign-in");
  }

  return <main className={styles.page}>
    <section className={styles.hero}>
      <div><p className={styles.kicker}>MPSqre Build360 · v1.0.0</p><h1>Company & package administration</h1><p>Create customer companies, assign the package they purchased, invite the first Company Administrator and manage account activation.</p></div>
      <div className={styles.heroActions}><span className={styles.badge}>Platform administration</span><button className={`${styles.button} ${styles.buttonSecondary}`} onClick={() => void signOutPlatform()} type="button">Sign out</button></div>
    </section>

    <section className={styles.metrics}>
      <article className={styles.metric}><span>Companies</span><strong>{overview.summary.company_count}</strong></article>
      <article className={styles.metric}><span>Active companies</span><strong>{overview.summary.active_company_count}</strong></article>
      <article className={styles.metric}><span>Suspended</span><strong>{overview.summary.suspended_company_count}</strong></article>
      <article className={styles.metric}><span>Active people</span><strong>{overview.summary.membership_count}</strong></article>
      <article className={styles.metric}><span>Pending admin invites</span><strong>{overview.summary.pending_admin_invitation_count}</strong></article>
    </section>

    {error ? <p className={styles.error}>{error}</p> : null}
    {notice ? <p className={styles.notice}>{notice}</p> : null}
    {lastActivationUrl ? <div className={styles.notice}><strong>Secure activation link</strong><div className={styles.code}>{lastActivationUrl}</div><button className={`${styles.button} ${styles.buttonSecondary}`} onClick={() => void navigator.clipboard.writeText(lastActivationUrl)} type="button">Copy activation link</button></div> : null}

    <section className={styles.operatorOnlyNotice}>
      <strong>Platform operations:</strong> Release, stability, go-live and cloud controls are managed only by Build360 Super Admin and are not included in customer packages.
    </section>

    <section className={styles.controlDeck}>
      <section className={`${styles.panel} ${styles.portfolioPanel}`} id="tenant-portfolio">
        <div className={styles.sectionHeading}>
          <div><p className={styles.kicker}>Customer portfolio</p><h2>Companies</h2><p className={styles.panelIntro}>Select a company and manage its package in the adjacent control panel.</p></div>
          <span className={styles.sectionCount}>{overview.companies.length} tenants</span>
        </div>
        <div className={styles.tableWrap}><table className={`${styles.table} ${styles.portfolioTable}`}><thead><tr><th>Company</th><th>Plan</th><th>People</th><th>Status</th><th>Primary admin</th><th>Actions</th></tr></thead><tbody>{overview.companies.map((company) => <tr className={selectedCompanyId === company.public_id ? styles.selectedRow : ""} key={company.public_id}><td><strong>{company.display_name}</strong><div className={styles.subtle}>{company.code} · {company.currency}</div><div className={styles.subtle}>{company.onboarding_status_code}</div></td><td>{company.plan_code || "Not assigned"}</td><td>{company.membership_count}</td><td><span className={`${styles.pill} ${company.is_active ? styles.pillActive : styles.pillDanger}`}>{company.is_active ? "ACTIVE" : "SUSPENDED"}</span></td><td>{company.primary_admin ? <div><strong>{company.primary_admin.display_name || company.primary_admin.email}</strong><div className={styles.subtle}>{company.primary_admin.email}</div><span className={`${styles.pill} ${company.primary_admin.status === "ACTIVE" ? styles.pillActive : styles.pillDanger}`}>{company.primary_admin.status.replaceAll("_", " ")}</span>{company.primary_admin.status === "ACTIVE" ? null : <button className={`${styles.linkButton}`} disabled={busy} onClick={() => void regeneratePrimaryAdminInvite(company)} type="button">Resend activation email</button>}</div> : <span className={styles.subtle}>Not configured</span>}</td><td><div className={styles.rowActions}><button className={`${styles.button} ${selectedCompanyId === company.public_id ? styles.buttonCurrent : styles.buttonSecondary}`} onClick={() => openPackage(company.public_id)} type="button">{selectedCompanyId === company.public_id ? "Package open" : "Open package"}</button><button className={`${styles.button} ${company.is_active ? styles.buttonDanger : styles.buttonSecondary}`} disabled={busy} onClick={() => void setStatus(company)} type="button">{company.is_active ? "Suspend" : "Activate"}</button></div></td></tr>)}</tbody></table></div>
      </section>

      <section className={`${styles.panel} ${styles.featurePanel}`} id="tenant-package-control">
        <div className={styles.packageTopbar}>
          <div>
            <p className={styles.kicker}>Subscription control</p>
            <h2>Package control</h2>
            <p className={styles.panelIntro}>Core modules and add-ons are organized by product hierarchy instead of raw entitlement groups.</p>
          </div>
          <div className={styles.featureControls}>
            <label>Company<select value={selectedCompanyId} onChange={(event) => setSelectedCompanyId(event.target.value)}>{overview.companies.map((company) => <option key={company.public_id} value={company.public_id}>{company.display_name} · {company.code}</option>)}</select></label>
            <label>Reason code<input value={reasonCode} onChange={(event) => setReasonCode(event.target.value)} placeholder="subscription-change" /></label>
          </div>
        </div>

        {matrixLoading ? <div className={styles.empty}>Loading SaaS package…</div> : null}
        {!matrixLoading && matrix ? <>
          <div className={styles.subscriptionStrip}><span><strong>{matrix.company.display_name}</strong> · {matrix.company.code}</span><span>Subscription <strong>{matrix.subscription.status}</strong></span><span>Plan <strong>{matrix.subscription.plan_code || "No published plan"}{matrix.subscription.plan_version ? ` v${matrix.subscription.plan_version}` : ""}</strong></span><span><strong>{moduleSummary.enabled}/{moduleSummary.total}</strong> modules enabled</span></div>

          <div className={styles.presetBar}>
            <div><strong>Package preset</strong><span>Apply a baseline package, then fine-tune only what this customer purchased.</span></div>
            <select value={presetCode} onChange={(event) => setPresetCode(event.target.value)}>{matrix.presets.map((preset) => <option key={preset.code} value={preset.code}>{preset.label}</option>)}</select>
            <button className={styles.button} disabled={presetBusy || Boolean(featureBusy)} onClick={() => void applyPreset()} type="button">{presetBusy ? "Applying…" : "Apply package"}</button>
          </div>

          <div className={styles.packageWorkspace}>
            <nav className={styles.packageNav} aria-label="Package module groups">
              <p className={styles.packageNavLabel}>Product areas</p>
              {featureSections.map((section) => {
                const sectionFeatures = [...(section.parent ? [section.parent] : []), ...section.items];
                const enabledCount = sectionFeatures.filter((item) => item.enabled).length;
                return <button className={`${styles.packageNavItem} ${selectedFeatureSection?.id === section.id ? styles.packageNavItemActive : ""}`} key={section.id} onClick={() => setActiveFeatureSection(section.id)} type="button"><span><strong>{section.label}</strong><small>{section.description}</small></span><em>{enabledCount}/{sectionFeatures.length}</em></button>;
              })}
            </nav>

            <div className={styles.packageContent}>
              {selectedFeatureSection ? <>
                <div className={styles.packageContentHeader}><div><p className={styles.kicker}>Selected product area</p><h3>{selectedFeatureSection.label}</h3><p>{selectedFeatureSection.description}</p></div></div>
                <div className={styles.featureList}>
                  {selectedFeatureSection.parent ? <>
                    <div className={styles.featureParentLabel}>Core module</div>
                    {renderFeatureRow(selectedFeatureSection.parent)}
                    {selectedFeatureSection.items.length ? <div className={styles.featureParentLabel}>Add-ons</div> : null}
                    {selectedFeatureSection.items.map((item) => renderFeatureRow(item, true))}
                  </> : selectedFeatureSection.items.map((item) => renderFeatureRow(item))}
                </div>
              </> : <div className={styles.empty}>No tenant features are configured.</div>}
            </div>
          </div>
        </> : null}
      </section>
    </section>

    <details className={`${styles.panel} ${styles.createCompanyPanel}`} id="new-company">
      <summary className={styles.createCompanySummary}>
        <span><strong>Create customer company</strong><small>Provision a new tenant, initial SaaS package and primary Company Administrator.</small></span>
        <span className={styles.summaryAction}>+ New company</span>
      </summary>
      <div className={styles.createCompanyBody}>
        <p className={styles.panelIntro}>Create the company, choose its starting package and send the first administrator invitation by email.</p>
        <form onSubmit={createCompany}><div className={styles.formGrid}>
          <div className={styles.field}><label>Company code</label><input name="code" required placeholder="ACME" /></div>
          <div className={styles.field}><label>Commercial plan code</label><input name="plan_code" defaultValue="PILOT_360" /></div>
          <div className={`${styles.field} ${styles.fieldFull}`}><label>Initial package</label><select name="preset_code" defaultValue="CRM_ONLY"><option value="CRM_ONLY">CRM only</option><option value="CONSTRUCTION_CORE">Construction core</option><option value="FULL_BUILD360">Full Build360</option></select></div>
          <div className={`${styles.field} ${styles.fieldFull}`}><label>Legal name</label><input name="legal_name" required /></div>
          <div className={`${styles.field} ${styles.fieldFull}`}><label>Display name</label><input name="display_name" required /></div>
          <div className={styles.field}><label>Locale</label><input name="locale" defaultValue="en-IN" required /></div>
          <div className={styles.field}><label>Timezone</label><input name="timezone" defaultValue="Asia/Kolkata" required /></div>
          <div className={styles.field}><label>Currency</label><input name="currency" defaultValue="INR" required maxLength={3} /></div>
          <div className={styles.field}><label>Unit system</label><input name="unit_system_code" defaultValue="METRIC" required /></div>
          <div className={styles.field}><label>Fiscal year start month</label><input name="fiscal_year_start_month" type="number" min="1" max="12" defaultValue="4" required /></div>
          <div className={styles.field}><label>Admin employee number</label><input name="admin_employee_number" placeholder="ADMIN-001" /></div>
          <div className={styles.field}><label>Company admin name</label><input name="admin_display_name" required /></div>
          <div className={styles.field}><label>Company admin email</label><input name="admin_email" type="email" required /></div>
        </div><div className={styles.actions}><button className={styles.button} disabled={busy} type="submit">{busy ? "Creating…" : "Create company & send invite"}</button></div></form>
      </div>
    </details>
  </main>;
}
