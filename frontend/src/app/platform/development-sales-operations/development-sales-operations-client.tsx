"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";

import styles from "./development-sales-operations.module.css";

type Row = Record<string, unknown>;
type Overview = {
  company: { name: string; code: string; timezone: string; currency: string };
  policy: { status: string; version: number; reservation_expiry_hours: number; collection_grace_days: number; handover_alert_days: number };
  metrics: Record<string, string | number>;
  inventories: Row[];
  units: Row[];
  buyers: Row[];
  reservations: Row[];
  bookings: Row[];
  milestones: Row[];
  receipts: Row[];
  commissions: Row[];
  handovers: Row[];
  portfolio: { unit_status: Row[]; booking_status: Row[]; collection_status: Row[] };
};

type Tab = "summary" | "inventory" | "customers" | "bookings" | "collections" | "handover";
type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>;
type FormState = Record<string, string>;

const emptyInventory = { code: "", name: "", development_type_code: "RESIDENTIAL", launch_on: "", currency_code: "", status_code: "LAUNCHED" } satisfies FormState;
const emptyUnit = { inventory_public_id: "", code: "", name: "", unit_type_code: "APARTMENT", tower_reference: "", floor_reference: "", carpet_area: "", saleable_area: "", area_unit_code: "SQ_M", list_price: "", currency_code: "", tax_code: "", status_code: "AVAILABLE" } satisfies FormState;
const emptyBuyer = { account_code: "", legal_name: "", display_name: "", buyer_type_code: "INDIVIDUAL", contact_name: "", contact_email: "", contact_phone: "", tax_reference: "" } satisfies FormState;
const emptyReservation = { unit_public_id: "", buyer_public_id: "", reservation_number: "", token_amount: "0", source_code: "DIRECT", expires_at: "" } satisfies FormState;
const emptyBooking = { unit_public_id: "", buyer_public_id: "", reservation_public_id: "", booking_number: "", booking_date: "", agreement_date: "", base_price: "", discount_amount: "0", tax_amount: "0", other_charges: "0", total_consideration: "", currency_code: "" } satisfies FormState;
const emptyMilestone = { booking_public_id: "", sequence: "1", milestone_code: "", description: "", due_on: "", percentage: "", amount: "", tax_amount: "0" } satisfies FormState;
const emptyReceipt = { booking_public_id: "", milestone_public_id: "", receipt_number: "", receipt_date: "", amount: "", currency_code: "", payment_method_code: "BANK_TRANSFER", payment_reference: "", finance_reference: "" } satisfies FormState;
const emptyCommission = { booking_public_id: "", broker_reference: "", broker_name: "", commission_percent: "0", commission_amount: "", currency_code: "" } satisfies FormState;
const emptyHandover = { booking_public_id: "", planned_on: "", open_defect_count: "0", checklist_reference: "", evidence_reference: "" } satisfies FormState;

function value(input: unknown): string {
  if (input === null || input === undefined) return "";
  return String(input);
}

function nullable(input: string): string | null {
  return input.trim() ? input.trim() : null;
}

function decimal(input: string): string {
  return input.trim() || "0";
}

function displayDate(input: unknown): string {
  const raw = value(input);
  if (!raw) return "—";
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleDateString();
}

function messageFrom(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.message === "string") return record.message;
  if (typeof record.detail === "string") return record.detail;
  const first = Object.values(record).find((item) => typeof item === "string" || Array.isArray(item));
  if (typeof first === "string") return first;
  if (Array.isArray(first)) return first.map(String).join(" ");
  return fallback;
}

function Metric({ label, metric, note }: { label: string; metric: string | number | undefined; note: string }) {
  return <article className={styles.metric}><span>{label}</span><strong>{metric ?? "—"}</strong><small>{note}</small></article>;
}

function Status({ label }: { label: string }) {
  return <span className={styles.pill}>{label || "—"}</span>;
}

function Field({ label, children, wide = false }: { label: string; children?: ReactNode; wide?: boolean }) {
  return <label className={wide ? styles.full : undefined}><span>{label}</span>{children}</label>;
}

function update<T extends FormState>(setter: Dispatch<SetStateAction<T>>, form: T) {
  return (event: InputEvent) =>
    setter({ ...form, [event.target.name]: event.target.value } as T);
}

function nextBooking(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "ACTIVE";
  if (status === "HANDED_OVER") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextReceipt(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "CONFIRMED";
  if (status === "CONFIRMED") return "REVERSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextCommission(status: string): string {
  if (status === "DRAFT") return "SUBMITTED";
  if (status === "SUBMITTED") return "APPROVED";
  if (status === "APPROVED") return "PAYABLE";
  if (status === "PAYABLE") return "PAID";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

function nextHandover(status: string): string {
  if (status === "DRAFT") return "READINESS_REVIEW";
  if (status === "READINESS_REVIEW") return "READY";
  if (status === "READY") return "OFFERED";
  if (status === "OFFERED") return "POSSESSED";
  if (status === "POSSESSED") return "CLOSED";
  if (status === "REJECTED") return "DRAFT";
  return "";
}

export function DevelopmentSalesOperationsClient() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [inventoryForm, setInventoryForm] = useState(emptyInventory);
  const [unitForm, setUnitForm] = useState(emptyUnit);
  const [buyerForm, setBuyerForm] = useState(emptyBuyer);
  const [reservationForm, setReservationForm] = useState(emptyReservation);
  const [bookingForm, setBookingForm] = useState(emptyBooking);
  const [milestoneForm, setMilestoneForm] = useState(emptyMilestone);
  const [receiptForm, setReceiptForm] = useState(emptyReceipt);
  const [commissionForm, setCommissionForm] = useState(emptyCommission);
  const [handoverForm, setHandoverForm] = useState(emptyHandover);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/platform/development-sales-operations/overview", { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "Development sales operations could not be loaded."));
      setOverview(payload as Overview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Development sales operations could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh();
    });
    return () => controller.abort();
  }, [refresh]);

  async function post(path: string, body: Record<string, unknown>, success: string) {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`/api/platform/development-sales-operations/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(messageFrom(payload, "The request could not be completed."));
      setNotice(success);
      await refresh();
      return payload as Record<string, unknown>;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The request could not be completed.");
      return null;
    } finally {
      setWorking(false);
    }
  }

  const inventories = overview?.inventories ?? [];
  const units = useMemo(() => overview?.units ?? [], [overview?.units]);
  const buyers = overview?.buyers ?? [];
  const reservations = overview?.reservations ?? [];
  const bookings = overview?.bookings ?? [];
  const milestones = overview?.milestones ?? [];
  const receipts = overview?.receipts ?? [];
  const commissions = overview?.commissions ?? [];
  const handovers = overview?.handovers ?? [];
  const availableUnits = useMemo(() => units.filter((item) => ["AVAILABLE", "RELEASED", "RESERVED"].includes(value(item.status_code))), [units]);

  if (loading && !overview) {
    return <main className={styles.shell}><section className={styles.loading}>Preparing the development sales command centre…</section></main>;
  }

  if (!overview) {
    return <main className={styles.shell}><section className={styles.errorCard}><p className={styles.kicker}>SALES CONTROL UNAVAILABLE</p><h2>Development sales, booking and collections could not be opened.</h2><p>{error || "The request could not be completed."}</p><button type="button" onClick={() => void refresh()}>Retry workspace</button></section></main>;
  }

  const metrics = overview.metrics;
  const currency = overview.company.currency;

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className={styles.kicker}>MPSQRE BUILD360 · PHASE 42</p>
          <h1>Development sales, booking, collections & customer handover</h1>
          <p className={styles.lead}>Control real-estate inventory release, buyer reservations, governed bookings, milestone collections, channel commissions and possession from one tenant-safe revenue command centre.</p>
          <div className={styles.tags}><span>{overview.company.name}</span><span>{currency}</span><span>{overview.company.timezone}</span><span>Policy {overview.policy.status}</span></div>
        </div>
        <div className={styles.heroActions}><span className={styles.activeLabel}>PHASE 42 DEVELOPMENT SALES OPERATIONS ACTIVE</span><button type="button" onClick={() => void refresh()}>Refresh revenue cockpit</button></div>
      </header>

      {error ? <p className={styles.alert}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}

      <section className={styles.metrics} aria-label="Development sales metrics">
        <Metric label="Available inventory" metric={metrics.available_units} note={`${metrics.released_units} released units`} />
        <Metric label="Reservations" metric={metrics.reserved_units} note={`${metrics.expiring_reservations} expire inside ${overview.policy.reservation_expiry_hours} hours`} />
        <Metric label="Booked & sold" metric={metrics.booked_units} note={`${metrics.handed_over_units} handed over`} />
        <Metric label="Booking value" metric={`${currency} ${metrics.booking_value}`} note={`${currency} ${metrics.collected_amount} collected`} />
        <Metric label="Outstanding" metric={`${currency} ${metrics.outstanding_amount}`} note={`${metrics.overdue_milestones} overdue milestones`} />
        <Metric label="Handover watch" metric={metrics.pending_handovers} note={`${metrics.handovers_due} due inside ${overview.policy.handover_alert_days} days`} />
      </section>

      <nav className={styles.tabs} aria-label="Development sales operations tabs">
        {(["summary", "inventory", "customers", "bookings", "collections", "handover"] as Tab[]).map((item) => <button type="button" key={item} className={tab === item ? styles.selected : ""} onClick={() => setTab(item)}>{item === "customers" ? "Buyers & reservations" : item === "collections" ? "Collections & receipts" : item === "handover" ? "Commissions & handover" : item.charAt(0).toUpperCase() + item.slice(1)}</button>)}
      </nav>

      {tab === "summary" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>REVENUE POSITION</p><h2>Portfolio governance posture</h2><dl className={styles.definition}><div><dt>Developments</dt><dd>{inventories.length}</dd></div><div><dt>Saleable units</dt><dd>{units.length}</dd></div><div><dt>Buyer accounts</dt><dd>{buyers.length}</dd></div><div><dt>Active bookings</dt><dd>{bookings.filter((item) => ["APPROVED", "ACTIVE", "HANDED_OVER"].includes(value(item.status_code))).length}</dd></div><div><dt>Policy version</dt><dd>v{overview.policy.version}</dd></div></dl></article>
          <article className={styles.card}><p className={styles.kicker}>CONTROL ASSURANCE</p><h2>Operating controls</h2><dl className={styles.definition}><div><dt>Reservation hold</dt><dd>{overview.policy.reservation_expiry_hours} hours</dd></div><div><dt>Collection grace</dt><dd>{overview.policy.collection_grace_days} days</dd></div><div><dt>Handover alert</dt><dd>{overview.policy.handover_alert_days} days</dd></div><div><dt>Booking approval</dt><dd>Maker-checker</dd></div><div><dt>Payment provider</dt><dd>Provider-neutral</dd></div></dl></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>INVENTORY MIX</p><h2>Current unit status</h2><div className={styles.statusGrid}>{overview.portfolio.unit_status.map((row) => <div key={value(row.status_code)}><Status label={value(row.status_code)} /><strong>{value(row.count)}</strong></div>)}</div></article>
        </section>
      ) : null}

      {tab === "inventory" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>DEVELOPMENT MASTER</p><h2>Create sales inventory</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("inventories", { ...inventoryForm, launch_on: nullable(inventoryForm.launch_on), currency_code: inventoryForm.currency_code || undefined }, "Development inventory created.").then((result) => { if (result) setInventoryForm(emptyInventory); }); }}><div className={styles.formGrid}><Field label="Code"><input name="code" required value={inventoryForm.code} onChange={update(setInventoryForm, inventoryForm)} /></Field><Field label="Name"><input name="name" required value={inventoryForm.name} onChange={update(setInventoryForm, inventoryForm)} /></Field><Field label="Type"><select name="development_type_code" value={inventoryForm.development_type_code} onChange={update(setInventoryForm, inventoryForm)}><option>RESIDENTIAL</option><option>COMMERCIAL</option><option>MIXED_USE</option><option>PLOTTED</option></select></Field><Field label="Launch date"><input type="date" name="launch_on" value={inventoryForm.launch_on} onChange={update(setInventoryForm, inventoryForm)} /></Field><Field label="Status"><select name="status_code" value={inventoryForm.status_code} onChange={update(setInventoryForm, inventoryForm)}><option>PLANNING</option><option>LAUNCHED</option><option>ACTIVE</option></select></Field><Field label="Currency"><input name="currency_code" maxLength={3} placeholder={currency} value={inventoryForm.currency_code} onChange={update(setInventoryForm, inventoryForm)} /></Field></div><button disabled={working}>Create inventory</button></form></article>
          <article className={styles.card}><p className={styles.kicker}>UNIT RELEASE</p><h2>Register saleable unit</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("units", { ...unitForm, carpet_area: nullable(unitForm.carpet_area), saleable_area: nullable(unitForm.saleable_area), list_price: decimal(unitForm.list_price), currency_code: unitForm.currency_code || undefined }, "Saleable unit registered.").then((result) => { if (result) setUnitForm(emptyUnit); }); }}><div className={styles.formGrid}><Field label="Development" wide><select name="inventory_public_id" required value={unitForm.inventory_public_id} onChange={update(setUnitForm, unitForm)}><option value="">Select development</option>{inventories.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.code)} · {value(item.name)}</option>)}</select></Field><Field label="Unit code"><input name="code" required value={unitForm.code} onChange={update(setUnitForm, unitForm)} /></Field><Field label="Unit name"><input name="name" required value={unitForm.name} onChange={update(setUnitForm, unitForm)} /></Field><Field label="Tower"><input name="tower_reference" value={unitForm.tower_reference} onChange={update(setUnitForm, unitForm)} /></Field><Field label="Floor"><input name="floor_reference" value={unitForm.floor_reference} onChange={update(setUnitForm, unitForm)} /></Field><Field label="Saleable area"><input type="number" step="0.001" name="saleable_area" value={unitForm.saleable_area} onChange={update(setUnitForm, unitForm)} /></Field><Field label="List price"><input type="number" step="0.01" name="list_price" required value={unitForm.list_price} onChange={update(setUnitForm, unitForm)} /></Field></div><button disabled={working}>Release unit</button></form></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>INVENTORY REGISTER</p><h2>Development unit portfolio</h2><div className={styles.tableWrap}><table><thead><tr><th>Development</th><th>Unit</th><th>Type</th><th>Location</th><th>Area</th><th>List price</th><th>Status</th></tr></thead><tbody>{units.map((item) => <tr key={value(item.public_id)}><td>{value(item.inventory__code)}</td><td><strong>{value(item.code)}</strong><small>{value(item.name)}</small></td><td>{value(item.unit_type_code)}</td><td>{value(item.tower_reference)} {value(item.floor_reference)}</td><td>{value(item.saleable_area)} {value(item.area_unit_code)}</td><td>{value(item.currency_code)} {value(item.list_price)}</td><td><Status label={value(item.status_code)} /></td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "customers" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>BUYER MASTER</p><h2>Create buyer account</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("buyers", buyerForm, "Buyer account created.").then((result) => { if (result) setBuyerForm(emptyBuyer); }); }}><div className={styles.formGrid}><Field label="Account code"><input name="account_code" required value={buyerForm.account_code} onChange={update(setBuyerForm, buyerForm)} /></Field><Field label="Buyer type"><select name="buyer_type_code" value={buyerForm.buyer_type_code} onChange={update(setBuyerForm, buyerForm)}><option>INDIVIDUAL</option><option>JOINT</option><option>ORGANIZATION</option><option>INVESTOR</option></select></Field><Field label="Legal name"><input name="legal_name" required value={buyerForm.legal_name} onChange={update(setBuyerForm, buyerForm)} /></Field><Field label="Display name"><input name="display_name" required value={buyerForm.display_name} onChange={update(setBuyerForm, buyerForm)} /></Field><Field label="Email"><input type="email" name="contact_email" value={buyerForm.contact_email} onChange={update(setBuyerForm, buyerForm)} /></Field><Field label="Phone"><input name="contact_phone" value={buyerForm.contact_phone} onChange={update(setBuyerForm, buyerForm)} /></Field></div><button disabled={working}>Create buyer</button></form></article>
          <article className={styles.card}><p className={styles.kicker}>UNIT HOLD</p><h2>Create reservation</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("reservations", { ...reservationForm, token_amount: decimal(reservationForm.token_amount), expires_at: nullable(reservationForm.expires_at) }, "Unit reservation created.").then((result) => { if (result) setReservationForm(emptyReservation); }); }}><div className={styles.formGrid}><Field label="Unit" wide><select name="unit_public_id" required value={reservationForm.unit_public_id} onChange={update(setReservationForm, reservationForm)}><option value="">Select available unit</option>{availableUnits.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.inventory__code)} · {value(item.code)}</option>)}</select></Field><Field label="Buyer" wide><select name="buyer_public_id" required value={reservationForm.buyer_public_id} onChange={update(setReservationForm, reservationForm)}><option value="">Select buyer</option>{buyers.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.account_code)} · {value(item.display_name)}</option>)}</select></Field><Field label="Reservation number"><input name="reservation_number" required value={reservationForm.reservation_number} onChange={update(setReservationForm, reservationForm)} /></Field><Field label="Token amount"><input type="number" step="0.01" name="token_amount" value={reservationForm.token_amount} onChange={update(setReservationForm, reservationForm)} /></Field><Field label="Expiry"><input type="datetime-local" name="expires_at" value={reservationForm.expires_at} onChange={update(setReservationForm, reservationForm)} /></Field><Field label="Source"><input name="source_code" value={reservationForm.source_code} onChange={update(setReservationForm, reservationForm)} /></Field></div><button disabled={working}>Reserve unit</button></form></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>RESERVATION REGISTER</p><h2>Active and historical reservations</h2><div className={styles.tableWrap}><table><thead><tr><th>Reservation</th><th>Buyer</th><th>Unit</th><th>Reserved</th><th>Expires</th><th>Token</th><th>Status</th><th>Control</th></tr></thead><tbody>{reservations.map((item) => <tr key={value(item.public_id)}><td><strong>{value(item.reservation_number)}</strong><small>{value(item.source_code)}</small></td><td>{value(item.buyer__display_name)}</td><td>{value(item.unit__inventory__code)} · {value(item.unit__code)}</td><td>{displayDate(item.reserved_at)}</td><td>{displayDate(item.expires_at)}</td><td>{value(item.currency_code)} {value(item.token_amount)}</td><td><Status label={value(item.status_code)} /></td><td>{value(item.status_code) === "ACTIVE" ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`reservations/${value(item.public_id)}/transition`, { status_code: "CANCELLED", expected_version: Number(item.version), note: "Cancelled from control room" }, "Reservation cancelled.")}>Cancel</button> : "—"}</td></tr>)}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "bookings" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>BOOKING CONTROL</p><h2>Create booking agreement</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("bookings", { ...bookingForm, reservation_public_id: nullable(bookingForm.reservation_public_id), agreement_date: nullable(bookingForm.agreement_date), base_price: decimal(bookingForm.base_price), discount_amount: decimal(bookingForm.discount_amount), tax_amount: decimal(bookingForm.tax_amount), other_charges: decimal(bookingForm.other_charges), total_consideration: bookingForm.total_consideration.trim() || undefined, currency_code: bookingForm.currency_code || undefined }, "Booking agreement created.").then((result) => { if (result) setBookingForm(emptyBooking); }); }}><div className={styles.formGrid}><Field label="Unit"><select name="unit_public_id" required value={bookingForm.unit_public_id} onChange={update(setBookingForm, bookingForm)}><option value="">Select unit</option>{availableUnits.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.inventory__code)} · {value(item.code)}</option>)}</select></Field><Field label="Buyer"><select name="buyer_public_id" required value={bookingForm.buyer_public_id} onChange={update(setBookingForm, bookingForm)}><option value="">Select buyer</option>{buyers.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.display_name)}</option>)}</select></Field><Field label="Reservation"><select name="reservation_public_id" value={bookingForm.reservation_public_id} onChange={update(setBookingForm, bookingForm)}><option value="">Direct booking</option>{reservations.filter((item) => value(item.status_code) === "ACTIVE").map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.reservation_number)}</option>)}</select></Field><Field label="Booking number"><input name="booking_number" required value={bookingForm.booking_number} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Booking date"><input type="date" name="booking_date" required value={bookingForm.booking_date} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Base price"><input type="number" step="0.01" name="base_price" required value={bookingForm.base_price} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Discount"><input type="number" step="0.01" name="discount_amount" value={bookingForm.discount_amount} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Tax"><input type="number" step="0.01" name="tax_amount" value={bookingForm.tax_amount} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Other charges"><input type="number" step="0.01" name="other_charges" value={bookingForm.other_charges} onChange={update(setBookingForm, bookingForm)} /></Field><Field label="Total consideration"><input type="number" step="0.01" name="total_consideration" placeholder="Auto-calculated" value={bookingForm.total_consideration} onChange={update(setBookingForm, bookingForm)} /></Field></div><button disabled={working}>Create booking</button></form></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>BOOKING REGISTER</p><h2>Governed customer bookings</h2><div className={styles.tableWrap}><table><thead><tr><th>Booking</th><th>Buyer</th><th>Unit</th><th>Date</th><th>Consideration</th><th>Status</th><th>Control</th></tr></thead><tbody>{bookings.map((item) => { const next = nextBooking(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.booking_number)}</td><td>{value(item.buyer__display_name)}</td><td>{value(item.unit__inventory__code)} · {value(item.unit__code)}</td><td>{displayDate(item.booking_date)}</td><td>{value(item.currency_code)} {value(item.total_consideration)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`bookings/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: "Advanced from development sales control room" }, `Booking moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "collections" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>PAYMENT PLAN</p><h2>Create collection milestone</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("milestones", { ...milestoneForm, sequence: Number(milestoneForm.sequence), percentage: nullable(milestoneForm.percentage), amount: decimal(milestoneForm.amount), tax_amount: decimal(milestoneForm.tax_amount) }, "Payment milestone created.").then((result) => { if (result) setMilestoneForm(emptyMilestone); }); }}><div className={styles.formGrid}><Field label="Booking" wide><select name="booking_public_id" required value={milestoneForm.booking_public_id} onChange={update(setMilestoneForm, milestoneForm)}><option value="">Select booking</option>{bookings.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.booking_number)} · {value(item.buyer__display_name)}</option>)}</select></Field><Field label="Sequence"><input type="number" min="1" name="sequence" value={milestoneForm.sequence} onChange={update(setMilestoneForm, milestoneForm)} /></Field><Field label="Code"><input name="milestone_code" required value={milestoneForm.milestone_code} onChange={update(setMilestoneForm, milestoneForm)} /></Field><Field label="Description" wide><input name="description" required value={milestoneForm.description} onChange={update(setMilestoneForm, milestoneForm)} /></Field><Field label="Due date"><input type="date" name="due_on" required value={milestoneForm.due_on} onChange={update(setMilestoneForm, milestoneForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={milestoneForm.amount} onChange={update(setMilestoneForm, milestoneForm)} /></Field></div><button disabled={working}>Create milestone</button></form></article>
          <article className={styles.card}><p className={styles.kicker}>COLLECTION EVIDENCE</p><h2>Record receipt</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("receipts", { ...receiptForm, milestone_public_id: nullable(receiptForm.milestone_public_id), amount: decimal(receiptForm.amount), currency_code: receiptForm.currency_code || undefined }, "Collection receipt recorded.").then((result) => { if (result) setReceiptForm(emptyReceipt); }); }}><div className={styles.formGrid}><Field label="Booking" wide><select name="booking_public_id" required value={receiptForm.booking_public_id} onChange={update(setReceiptForm, receiptForm)}><option value="">Select approved booking</option>{bookings.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.booking_number)}</option>)}</select></Field><Field label="Milestone" wide><select name="milestone_public_id" value={receiptForm.milestone_public_id} onChange={update(setReceiptForm, receiptForm)}><option value="">Unallocated receipt</option>{milestones.filter((item) => !receiptForm.booking_public_id || value(item.booking__public_id) === receiptForm.booking_public_id).map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.milestone_code)} · {value(item.outstanding)} outstanding</option>)}</select></Field><Field label="Receipt number"><input name="receipt_number" required value={receiptForm.receipt_number} onChange={update(setReceiptForm, receiptForm)} /></Field><Field label="Receipt date"><input type="date" name="receipt_date" required value={receiptForm.receipt_date} onChange={update(setReceiptForm, receiptForm)} /></Field><Field label="Amount"><input type="number" step="0.01" name="amount" required value={receiptForm.amount} onChange={update(setReceiptForm, receiptForm)} /></Field><Field label="Payment method"><select name="payment_method_code" value={receiptForm.payment_method_code} onChange={update(setReceiptForm, receiptForm)}><option>BANK_TRANSFER</option><option>CHEQUE</option><option>CARD</option><option>CASH</option><option>PAYMENT_GATEWAY</option></select></Field></div><button disabled={working}>Record receipt</button></form></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>COLLECTION REGISTER</p><h2>Payment milestones and receipts</h2><div className={styles.tableWrap}><table><thead><tr><th>Booking</th><th>Milestone</th><th>Due</th><th>Total</th><th>Paid</th><th>Outstanding</th><th>Status</th></tr></thead><tbody>{milestones.map((item) => <tr key={value(item.public_id)}><td>{value(item.booking__booking_number)}</td><td>{value(item.sequence)} · {value(item.milestone_code)}</td><td>{displayDate(item.due_on)}</td><td>{currency} {value(item.total_due)}</td><td>{currency} {value(item.paid_amount)}</td><td>{currency} {value(item.outstanding)}</td><td><Status label={value(item.status_code)} /></td></tr>)}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Receipt</th><th>Booking</th><th>Date</th><th>Amount</th><th>Method</th><th>Status</th><th>Control</th></tr></thead><tbody>{receipts.map((item) => { const next = nextReceipt(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.receipt_number)}</td><td>{value(item.booking__booking_number)}</td><td>{displayDate(item.receipt_date)}</td><td>{value(item.currency_code)} {value(item.amount)}</td><td>{value(item.payment_method_code)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`receipts/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: "Collection control transition" }, `Receipt moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}

      {tab === "handover" ? (
        <section className={styles.grid}>
          <article className={styles.card}><p className={styles.kicker}>CHANNEL GOVERNANCE</p><h2>Register broker commission</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("commissions", { ...commissionForm, commission_percent: decimal(commissionForm.commission_percent), commission_amount: decimal(commissionForm.commission_amount), currency_code: commissionForm.currency_code || undefined }, "Broker commission registered.").then((result) => { if (result) setCommissionForm(emptyCommission); }); }}><div className={styles.formGrid}><Field label="Booking" wide><select name="booking_public_id" required value={commissionForm.booking_public_id} onChange={update(setCommissionForm, commissionForm)}><option value="">Select booking</option>{bookings.map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.booking_number)}</option>)}</select></Field><Field label="Broker reference"><input name="broker_reference" required value={commissionForm.broker_reference} onChange={update(setCommissionForm, commissionForm)} /></Field><Field label="Broker name"><input name="broker_name" required value={commissionForm.broker_name} onChange={update(setCommissionForm, commissionForm)} /></Field><Field label="Commission %"><input type="number" step="0.0001" name="commission_percent" value={commissionForm.commission_percent} onChange={update(setCommissionForm, commissionForm)} /></Field><Field label="Commission amount"><input type="number" step="0.01" name="commission_amount" required value={commissionForm.commission_amount} onChange={update(setCommissionForm, commissionForm)} /></Field></div><button disabled={working}>Register commission</button></form></article>
          <article className={styles.card}><p className={styles.kicker}>CUSTOMER POSSESSION</p><h2>Create handover record</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void post("handovers", { booking_public_id: handoverForm.booking_public_id, planned_on: nullable(handoverForm.planned_on), open_defect_count: Number(handoverForm.open_defect_count), checklist: handoverForm.checklist_reference ? { reference: handoverForm.checklist_reference } : {}, evidence: handoverForm.evidence_reference ? { reference: handoverForm.evidence_reference } : {} }, "Customer handover record created.").then((result) => { if (result) setHandoverForm(emptyHandover); }); }}><div className={styles.formGrid}><Field label="Active booking" wide><select name="booking_public_id" required value={handoverForm.booking_public_id} onChange={update(setHandoverForm, handoverForm)}><option value="">Select active booking</option>{bookings.filter((item) => value(item.status_code) === "ACTIVE").map((item) => <option key={value(item.public_id)} value={value(item.public_id)}>{value(item.booking_number)} · {value(item.buyer__display_name)}</option>)}</select></Field><Field label="Planned handover"><input type="date" name="planned_on" value={handoverForm.planned_on} onChange={update(setHandoverForm, handoverForm)} /></Field><Field label="Open defects"><input type="number" min="0" name="open_defect_count" value={handoverForm.open_defect_count} onChange={update(setHandoverForm, handoverForm)} /></Field><Field label="Checklist reference"><input name="checklist_reference" value={handoverForm.checklist_reference} onChange={update(setHandoverForm, handoverForm)} /></Field><Field label="Evidence reference"><input name="evidence_reference" value={handoverForm.evidence_reference} onChange={update(setHandoverForm, handoverForm)} /></Field></div><button disabled={working}>Create handover</button></form></article>
          <article className={`${styles.card} ${styles.wide}`}><p className={styles.kicker}>BROKER & HANDOVER CONTROL</p><h2>Commercial closure register</h2><div className={styles.tableWrap}><table><thead><tr><th>Booking</th><th>Broker</th><th>Commission</th><th>Status</th><th>Control</th></tr></thead><tbody>{commissions.map((item) => { const next = nextCommission(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.booking__booking_number)}</td><td><strong>{value(item.broker_name)}</strong><small>{value(item.broker_reference)}</small></td><td>{value(item.currency_code)} {value(item.commission_amount)} · {value(item.commission_percent)}%</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`commissions/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: "Commission control transition" }, `Commission moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div><div className={styles.tableWrap}><table><thead><tr><th>Booking</th><th>Buyer</th><th>Unit</th><th>Planned</th><th>Defects</th><th>Status</th><th>Control</th></tr></thead><tbody>{handovers.map((item) => { const next = nextHandover(value(item.status_code)); return <tr key={value(item.public_id)}><td>{value(item.booking__booking_number)}</td><td>{value(item.booking__buyer__display_name)}</td><td>{value(item.unit__inventory__code)} · {value(item.unit__code)}</td><td>{displayDate(item.planned_on)}</td><td>{value(item.open_defect_count)}</td><td><Status label={value(item.status_code)} /></td><td>{next ? <button className={styles.smallButton} type="button" disabled={working} onClick={() => void post(`handovers/${value(item.public_id)}/transition`, { status_code: next, expected_version: Number(item.version), note: "Customer handover transition" }, `Handover moved to ${next}.`)}>{next}</button> : "—"}</td></tr>; })}</tbody></table></div></article>
        </section>
      ) : null}
    </main>
  );
}
