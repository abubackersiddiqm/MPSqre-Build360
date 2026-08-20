import Link from "next/link";

type Company = {
  public_id: string;
  code: string;
  display_name: string;
  locale: string;
  timezone: string;
  currency: string;
};

type Entitlements = {
  subscription_status: string;
  plan_code: string | null;
  plan_version: number | null;
  entitlements: Record<string, boolean>;
  limits: Record<string, number | null>;
};

type ConfigurationItem = {
  public_id: string;
  definition_code: string;
  name: string;
  version: number;
  status: string;
  is_secret: boolean;
  payload?: unknown;
};

type Approval = {
  public_id: string;
  transition_code: string;
  from_state_code: string;
  to_state_code: string;
  due_at: string | null;
};

export type PlatformSummaryProps = {
  company: Company;
  permissions: string[];
  entitlements: Entitlements | null;
  features: Record<string, boolean>;
  configurations: ConfigurationItem[];
  approvals: Approval[];
  platformOperator: boolean;
};

function StatusPill({ children }: Readonly<{ children: string }>) {
  return (
    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-900">
      {children}
    </span>
  );
}

export function PlatformSummary({
  company,
  permissions,
  entitlements,
  features,
  configurations,
  approvals,
  platformOperator,
}: Readonly<PlatformSummaryProps>) {
  const enabledEntitlements = entitlements
    ? Object.values(entitlements.entitlements).filter(Boolean).length
    : 0;
  const canOpenWhiteLabel =
    features["tenant.white_label"] === true &&
    (permissions.includes("tenant.branding.read") || permissions.includes("tenant.domain.read"));
  const canManageUsers = permissions.includes("access.user.manage");

  return (
    <main className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">
              MPSqre Build360
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              {company.display_name}
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {company.code} · {company.currency} · {company.timezone}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill>WORKSPACE ACTIVE</StatusPill>
            {canManageUsers ? (
              <Link
                className="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white"
                href="/platform/access-control"
              >
                Users & permissions
              </Link>
            ) : null}
            <Link
              className="rounded-lg border border-[var(--border)] bg-white px-4 py-2 text-sm font-semibold"
              href="/workspaces"
            >
              Workspace launcher
            </Link>
            {platformOperator ? (
              <span className="rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-[var(--muted)]">
                Platform operator
              </span>
            ) : null}
          </div>
        </header>

        {canManageUsers ? (
          <section className="mb-5 grid gap-3 rounded-2xl border border-[var(--border)] bg-white p-4 shadow-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--brand)]">
                Company administration
              </p>
              <h2 className="mt-1 text-lg font-semibold">Users, permissions & audit history</h2>
              <p className="mt-1 text-sm leading-6 text-[var(--muted)]">
                Invite company users, apply module-level access and review every managed permission change.
              </p>
            </div>
            <Link
              className="rounded-lg border border-[var(--border)] bg-[var(--brand-soft)] px-4 py-2.5 text-center text-sm font-semibold text-[var(--brand)]"
              href="/platform/access-control"
            >
              Open user administration
            </Link>
          </section>
        ) : null}

        <section className="grid gap-3 py-5 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Access permissions</p>
            <p className="mt-2 text-3xl font-semibold">{permissions.length}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Active settings</p>
            <p className="mt-2 text-3xl font-semibold">{configurations.length}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Pending approvals</p>
            <p className="mt-2 text-3xl font-semibold">{approvals.length}</p>
          </article>
          <article className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
            <p className="text-sm text-[var(--muted)]">Available modules</p>
            <p className="mt-2 text-3xl font-semibold">{enabledEntitlements}</p>
          </article>
        </section>

        {canOpenWhiteLabel ? (
          <section className="mb-7 flex flex-col gap-5 rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--brand)]">White Label active</p>
              <h2 className="mt-2 text-xl font-semibold">Brand, domain & email</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">Manage company branding, custom domain and verified email delivery when White Label is enabled.</p>
            </div>
            <Link className="shrink-0 rounded-lg bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white" href="/brand-domain">Open White Label</Link>
          </section>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-2">
          <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-xl font-semibold">Workspace settings</h2>
              <span className="text-sm text-[var(--muted)]">Active settings</span>
            </div>
            {configurations.length ? (
              <ul className="mt-5 divide-y divide-[var(--border)]">
                {configurations.map((item) => (
                  <li className="flex items-center justify-between gap-4 py-4" key={item.public_id}>
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="mt-1 text-sm text-[var(--muted)]">
                        {item.definition_code} · v{item.version}
                      </p>
                    </div>
                    <span className="text-xs font-semibold uppercase text-[var(--brand)]">
                      {item.is_secret && item.payload === undefined ? "Protected" : item.status}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-5 text-sm leading-6 text-[var(--muted)]">
                No additional workspace settings are available for your account.
              </p>
            )}
          </article>

          <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Plan & access</h2>
            {entitlements ? (
              <dl className="mt-5 grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-[var(--muted)]">Status</dt>
                  <dd className="mt-1 font-semibold">{entitlements.subscription_status}</dd>
                </div>
                <div>
                  <dt className="text-sm text-[var(--muted)]">Plan</dt>
                  <dd className="mt-1 font-semibold">
                    {entitlements.plan_code
                      ? `${entitlements.plan_code} v${entitlements.plan_version}`
                      : "No active plan"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-5 text-sm leading-6 text-[var(--muted)]">
                Plan details are managed by your company administrator.
              </p>
            )}
          </article>

          <article className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-sm lg:col-span-2">
            <h2 className="text-xl font-semibold">Approvals</h2>
            {approvals.length ? (
              <ul className="mt-5 grid gap-3 md:grid-cols-2">
                {approvals.map((approval) => (
                  <li className="rounded-xl border border-[var(--border)] p-4" key={approval.public_id}>
                    <p className="font-medium">{approval.transition_code}</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {approval.from_state_code} → {approval.to_state_code}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-5 text-sm leading-6 text-[var(--muted)]">
                You have no pending approvals.
              </p>
            )}
          </article>
        </section>
      </div>
    </main>
  );
}
