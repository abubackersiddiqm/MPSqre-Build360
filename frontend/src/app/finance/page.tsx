import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { FinanceWorkspace, type Adjustment, type Budget, type Company, type FinanceSummary, type Invoice, type LedgerEntry, type Payment, type Period, type Project, type Variation } from "./workspace";

export const metadata: Metadata = { title: "Finance and commercial controls" };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function FinancePage() {
  const companyResult = await tenantBackendRequest<Company>("/companies/current");
  if (!companyResult.ok) redirect(companyResult.status === 401 ? "/sign-in" : "/select-company");
  const capabilityResult = await tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities");
  if (!capabilityResult.ok) redirect(capabilityResult.status === 401 ? "/sign-in" : "/select-company");
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("finance.dashboard.read")) redirect("/platform");
  const [summary, periods, budgets, variations, invoices, payments, adjustments, ledger, projects] = await Promise.all([
    tenantBackendRequest<FinanceSummary>("/finance/summary"),
    tenantBackendRequest<ListResponse<Period>>("/finance/periods"),
    tenantBackendRequest<ListResponse<Budget>>("/finance/budgets"),
    tenantBackendRequest<ListResponse<Variation>>("/finance/variations"),
    tenantBackendRequest<ListResponse<Invoice>>("/finance/invoices"),
    tenantBackendRequest<ListResponse<Payment>>("/finance/payments"),
    tenantBackendRequest<ListResponse<Adjustment>>("/finance/adjustments"),
    tenantBackendRequest<ListResponse<LedgerEntry>>("/finance/ledger"),
    tenantBackendRequest<ListResponse<Project>>("/projects/items"),
  ]);
  return <FinanceWorkspace company={companyResult.data} permissions={permissions} initialSummary={summary.ok ? summary.data : null} initialPeriods={periods.ok ? periods.data.items : []} initialBudgets={budgets.ok ? budgets.data.items : []} initialVariations={variations.ok ? variations.data.items : []} initialInvoices={invoices.ok ? invoices.data.items : []} initialPayments={payments.ok ? payments.data.items : []} initialAdjustments={adjustments.ok ? adjustments.data.items : []} initialLedger={ledger.ok ? ledger.data.items : []} projects={projects.ok ? projects.data.items : []} />;
}
