import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { tenantBackendRequest } from "@/lib/auth/tenant-backend";
import { SupplyWorkspace, type InventoryItem, type InventorySummary, type ProcurementSummary, type PurchaseRequest, type StockBalance, type Vendor, type VendorSummary, type Warehouse } from "./supply-workspace";

export const metadata: Metadata = { title: "Supply and inventory workspace" };
type Company = { public_id: string; code: string; display_name: string; currency: string; timezone: string };
type CapabilityResponse = { permissions: string[] };
type ListResponse<T> = { items: T[] };

export default async function SupplyPage() {
  const [companyResult, capabilityResult] = await Promise.all([tenantBackendRequest<Company>("/companies/current"), tenantBackendRequest<CapabilityResponse>("/companies/current/capabilities")]);
  if (!companyResult.ok || !capabilityResult.ok) {
    const status = !companyResult.ok ? companyResult.status : capabilityResult.status;
    redirect(status === 401 ? "/sign-in" : "/select-company");
  }
  const permissions = capabilityResult.data.permissions;
  if (!permissions.includes("procurement.dashboard.read") && !permissions.includes("inventory.dashboard.read") && !permissions.includes("vendor.dashboard.read")) redirect("/platform");
  const [vendorSummary, procurementSummary, inventorySummary, vendors, requests, items, warehouses, balances] = await Promise.all([
    tenantBackendRequest<VendorSummary>("/vendors/summary"),
    tenantBackendRequest<ProcurementSummary>("/procurement/summary"),
    tenantBackendRequest<InventorySummary>("/inventory/summary"),
    tenantBackendRequest<ListResponse<Vendor>>("/vendors/items"),
    tenantBackendRequest<ListResponse<PurchaseRequest>>("/procurement/requests"),
    tenantBackendRequest<ListResponse<InventoryItem>>("/inventory/items"),
    tenantBackendRequest<ListResponse<Warehouse>>("/inventory/warehouses"),
    tenantBackendRequest<ListResponse<StockBalance>>("/inventory/balances"),
  ]);
  return <SupplyWorkspace company={companyResult.data} permissions={permissions} initialVendorSummary={vendorSummary.ok ? vendorSummary.data : { vendors:0,qualified:0,pending:0,suspended:0 }} initialProcurementSummary={procurementSummary.ok ? procurementSummary.data : { purchase_requests:0,open_rfqs:0,quotes:0,purchase_orders:0,po_value:"0",unposted_receipts:0,currency:companyResult.data.currency }} initialInventorySummary={inventorySummary.ok ? inventorySummary.data : { items:0,warehouses:0,stock_positions:0,negative_positions:0,stock_value:"0",currency:companyResult.data.currency }} initialVendors={vendors.ok ? vendors.data.items : []} initialRequests={requests.ok ? requests.data.items : []} initialItems={items.ok ? items.data.items : []} initialWarehouses={warehouses.ok ? warehouses.data.items : []} initialBalances={balances.ok ? balances.data.items : []} />;
}
