"use client";

// The supplier portal's calls (server/app/routers/supplier.py, PF8). Every
// call names the supplier the person acts for (X-Truebex-Supplier) so a
// member of several suppliers switches without signing in again. Money is
// read as integer minor units and typed as decimal text in major units
// ("1299.00"); the server parses it with the currency's exponent.
import { api, API_URL, ApiError, getToken } from "@/lib/api";
import type { Money } from "@/lib/market";

export { formatMinor, formatMoney } from "@/lib/market";
export type { Money } from "@/lib/market";

const SUPPLIER_KEY = "truebex_supplier";
const CONTRACT = { "X-Truebex-Contract": "marketplace-api/1.1" };

export function getSupplierId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(SUPPLIER_KEY);
  } catch {
    return null;
  }
}

export function setSupplierId(id: string | null): void {
  try {
    if (id) window.localStorage.setItem(SUPPLIER_KEY, id);
    else window.localStorage.removeItem(SUPPLIER_KEY);
  } catch {
    /* storage blocked: the server picks the first supplier */
  }
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const id = getSupplierId();
  if (id) h.set("X-Truebex-Supplier", id);
  return h;
}

/** A portal call: JSON in and out, with the supplier header. */
function call<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  return api<T>(`/supplier${path}`, { ...init, headers: headers(init.headers) });
}

function upload<T>(path: string, form: FormData): Promise<T> {
  return api<T>(`/supplier${path}`, { method: "POST", body: form, headers: headers() });
}

/** The API's error `data` (field problems, rejected rows) when it sent some. */
export interface ErrorData {
  errors?: { row: number; sku?: string; variant_id?: string; column: string; code: string; value: string }[];
  missing?: string[];
  fields?: { field: string; message: string }[];
}

/** The server's JSON body of a failed portal call, read again for its `data`. */
export async function callWithData<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {}
): Promise<{ ok: true; data: T } | { ok: false; error: string; code: string; data: ErrorData | null }> {
  const h = headers(init.headers);
  const token = getToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  if (init.json !== undefined) h.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}/supplier${path}`, {
      ...init,
      headers: h,
      body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
    });
  } catch {
    return { ok: false, error: "Can't reach the Truebex server. Please try again in a moment.", code: "network", data: null };
  }
  const body = await res.json().catch(() => null);
  if (res.ok) return { ok: true, data: body as T };
  return {
    ok: false,
    error: typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`,
    code: typeof body?.code === "string" ? body.code : `http_${res.status}`,
    data: (body?.data as ErrorData) ?? null,
  };
}

// --- Types ---------------------------------------------------------------------

export type Role = "owner" | "catalogue" | "orders" | "viewer";

export interface SupplierInfo {
  supplier_id: string;
  name: string;
  legal_name: string | null;
  country: string;
  website: string | null;
  contact_email: string | null;
  status: "applied" | "verified" | "suspended";
  status_reason: string | null;
  listing_plan: string | null;
  regions: string[];
  payouts_connected: boolean;
  payouts_ready: boolean;
  orderable: boolean;
}

export interface Application {
  application_id: string;
  supplier_id: string;
  state: "applied" | "verified" | "declined";
  fields: Record<string, unknown>;
  documents: { sha256: string; bytes: number; name: string; uploaded_at: string }[];
  reason: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface Me {
  user: { id: number; email: string; name: string | null };
  memberships: { supplier_id: string; name: string; role: Role; status: string }[];
  supplier: SupplierInfo | null;
  role: Role | null;
  application: Application | null;
}

export interface FeedReport {
  feed_id: string;
  state: "queued" | "running" | "done" | "failed";
  rows: number;
  created: number;
  updated: number;
  unchanged: number;
  rejected: number;
  hidden: number;
  errors: { row: number; column: string; code: string; value: string }[];
  warnings: { row?: number; column: string; code: string; value?: string }[];
  format: string;
  mode: string;
  source: string;
  detail: string | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface FeedSource {
  url: string;
  format: string;
  mode: string;
  next_pull_at: string | null;
  last_pull_at: string | null;
  last_status: string | null;
  last_error: string | null;
  last_feed_id: string | null;
}

export interface Week {
  impressions: number;
  views: number;
  geometry_downloads: number;
  quotes: number;
  orders: number;
}

export interface Overview {
  supplier: SupplierInfo;
  role: Role;
  application: Application | null;
  open: { requests: number; orders: number };
  products: Record<string, number>;
  last_run: FeedReport | null;
  feed_source: FeedSource | null;
  week: Week;
}

export interface ProductSummary {
  product_id: string;
  sku: string;
  name: string;
  kind: string;
  category: string;
  status: string;
  review_note: string | null;
  thumbnail_url: string | null;
  variants: number;
  updated_at: string;
}

export interface Variant {
  variant_id: string;
  options: Record<string, string>;
  dims_mm: number[] | null;
  materials: string[];
  gtin: string | null;
  status: string;
  images: { sha256: string; url: string; thumb_url: string }[];
  geometry: {
    format: string;
    sha256: string;
    bytes: number;
    rev: number | null;
    check: { triangles: number | null; measured_mm: number[] | null; warnings: { code: string; detail: string }[] } | null;
  } | null;
  regions: string[];
}

export interface ProductFull extends Omit<ProductSummary, "variants"> {
  description: string;
  brand: string | null;
  app_path: string | null;
  images: string[];
  editable: boolean;
  variants: Variant[];
  approved_at: string | null;
  created_at: string | null;
}

export interface Category {
  path: string;
  label: string;
  app_path: string;
  products: number;
}

export interface MarketRegion {
  region: string;
  name: string;
  currency: string;
  exponent: number;
  tax: { name: string; rate_bp: number; prices_include_tax: boolean };
}

export interface RegionSetting extends MarketRegion {
  served: boolean;
  default_delivery_fee: string | null;
  delivery_days_min: number | null;
  delivery_days_max: number | null;
}

export interface PriceRow {
  product_id: string;
  sku: string;
  name: string;
  product_status: string;
  variant_id: string;
  options: Record<string, string>;
  variant_status: string;
  sold: boolean;
  price: string | null;
  amount: number | null;
  price_includes_tax: boolean;
  tax_rate_percent: string | null;
  delivery_fee: string | null;
  delivery_days_min: number | null;
  delivery_days_max: number | null;
  stock: number | null;
  lead_time_days: number | null;
  availability: string | null;
  source: string | null;
}

export interface PriceGrid {
  region: RegionSetting & { default_delivery_fee: string | null };
  served: string[];
  rows: PriceRow[];
}

export interface PriceRowIn {
  sku: string;
  variant_id: string;
  price: string;
  price_includes_tax: string;
  tax_rate_percent: string;
  delivery_fee: string;
  delivery_days_min: string;
  delivery_days_max: string;
  stock: string;
  lead_time_days: string;
  availability: string;
  status: string;
}

export interface DryRun {
  rows: number;
  created: number;
  updated: number;
  unchanged: number;
  rejected: number;
  hidden: number;
  errors: FeedReport["errors"];
  warnings: FeedReport["warnings"];
  new_products: number;
  new_variants: number;
}

export interface ImportItem {
  import_id: string;
  filename: string;
  format: string;
  mode: string;
  dry_run: DryRun;
  feed_id: string | null;
  run: FeedReport | null;
  created_at: string;
  expires_at: string | null;
  expired: boolean;
}

export interface InboxItem {
  order_id: string;
  ref: string;
  kind: "quote" | "order";
  order_state: string;
  state: string;
  payment: "platform" | "offline";
  region: string;
  currency: string;
  exponent: number;
  project: { name: string | null };
  buyer: { name: string | null; email: string | null; phone: string | null; message: string | null };
  delivery: { country?: string; city?: string | null; postcode?: string | null; address?: string | null };
  lines: {
    product_id: string;
    sku: string;
    variant_id: string;
    name: string;
    qty: number;
    unit: Money;
    quoted_unit: Money | null;
    includes_tax: boolean;
    tax_rate_bp: number;
    delivery_fee: Money | null;
  }[];
  subtotal: Money;
  delivery_fee: Money;
  tax: Money;
  total: Money;
  delivery_days: { min: number | null; max: number | null };
  quote: { quoted_at: string | null; valid_until: string | null; message: string | null } | null;
  shipment: { carrier: string; reference: string } | null;
  reason: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  open: boolean;
}

export interface AnalyticsCounts {
  impressions: number;
  views: number;
  geometry_downloads: number;
  quotes: number;
  orders: number;
}

export interface Analytics {
  from: string;
  to: string;
  region: string | null;
  days: (AnalyticsCounts & { day: string; order_value: Money[] })[];
  products: (AnalyticsCounts & { product_id: string; sku: string; name: string; order_value: Money[] })[];
  totals: AnalyticsCounts & { order_value: Money[] };
  regions: string[];
}

export interface ListingView {
  plan: string;
  commission_bp: number;
  currency: string;
  plans: { id: string; name: string; commission_bp: number; monthly_fee: Money | null }[];
  subscription: { plan: string; provider: string; status: string; amount: Money | null; detail: string | null } | null;
  billing: { interface: boolean; stripe_ready: boolean };
  payouts: { connected: boolean; ready: boolean; payments_enabled: boolean; stripe_configured: boolean };
  verified: boolean;
}

export interface Statements {
  statements: {
    statement_id: string;
    month: string;
    orders: number;
    commission: Money;
    listing_fee: Money;
    total: Money;
    state: string;
    invoice_ref: string | null;
    invoice_available: boolean;
  }[];
  commissions: { order_id: string; rate_bp: number; base: Money; amount: Money; state: string; created_at: string }[];
}

export interface Team {
  members: { user_id: number; email: string; name: string | null; role: Role; since: string }[];
  invites: { invite_id: string; email: string; role: Role; expires_at: string; expired: boolean }[];
  keys: {
    id: number;
    name: string;
    prefix: string;
    created_by: string | null;
    created_at: string;
    last_used_at: string | null;
    revoked_at: string | null;
  }[];
}

// --- Calls ------------------------------------------------------------------------

export const supplierApi = {
  me: () => call<Me>("/me"),
  apply: (json: Record<string, unknown>) => call<Application>("/applications", { method: "POST", json }),
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<Application["documents"][number]>("/documents", form);
  },
  overview: () => call<Overview>("/overview"),

  products: (status?: string, q?: string) => {
    const p = new URLSearchParams();
    if (status && status !== "all") p.set("status", status);
    if (q) p.set("q", q);
    const qs = p.toString();
    return call<{ products: ProductSummary[]; counts: Record<string, number> }>(`/products${qs ? `?${qs}` : ""}`);
  },
  createProduct: (json: Record<string, unknown>) => call<ProductFull>("/products", { method: "POST", json }),
  submitDrafts: () =>
    call<{ submitted: string[]; skipped: { sku: string; missing: string[] }[] }>("/products/submit", { method: "POST", json: {} }),
  product: (id: string) => call<ProductFull>(`/products/${encodeURIComponent(id)}`),
  editProduct: (id: string, json: Record<string, unknown>) =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}`, { method: "PATCH", json }),
  productAction: (id: string, action: "submit" | "hide" | "show" | "withdraw" | "discontinue") =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
  addVariant: (id: string, json: Record<string, unknown>) =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}/variants`, { method: "POST", json }),
  editVariant: (id: string, vid: string, json: Record<string, unknown>) =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}/variants/${encodeURIComponent(vid)}`, { method: "PATCH", json }),
  removeVariant: (id: string, vid: string) =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}/variants/${encodeURIComponent(vid)}`, { method: "DELETE" }),
  addImage: (id: string, vid: string, file: File) => {
    const form = new FormData();
    form.append("image", file);
    return upload<ProductFull>(`/products/${encodeURIComponent(id)}/variants/${encodeURIComponent(vid)}/images`, form);
  },
  removeImage: (id: string, vid: string, sha: string) =>
    call<ProductFull>(`/products/${encodeURIComponent(id)}/variants/${encodeURIComponent(vid)}/images/${sha}`, {
      method: "DELETE",
    }),
  uploadGeometry: (id: string, vid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("product_id", id);
    form.append("variant_id", vid);
    return upload<Variant & { check: NonNullable<Variant["geometry"]>["check"] }>("/geometry", form);
  },

  prices: (region?: string) => call<PriceGrid>(`/prices${region ? `?region=${encodeURIComponent(region)}` : ""}`),
  savePrices: (region: string, rows: Partial<PriceRowIn>[]) =>
    callWithData<PriceGrid & { saved: number }>(`/prices?region=${encodeURIComponent(region)}`, { method: "PUT", json: { rows } }),
  regions: () => call<{ regions: RegionSetting[] }>("/regions"),
  saveRegions: (regions: Record<string, unknown>[]) => call<{ regions: RegionSetting[] }>("/regions", { method: "PUT", json: { regions } }),

  imports: () => call<{ imports: ImportItem[]; runs: FeedReport[]; source: FeedSource | null }>("/imports"),
  uploadImport: (file: File, mode: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    return upload<ImportItem>("/imports", form);
  },
  importItem: (id: string) => call<ImportItem>(`/imports/${encodeURIComponent(id)}`),
  applyImport: (id: string) => call<ImportItem>(`/imports/${encodeURIComponent(id)}/apply`, { method: "POST" }),
  run: (feedId: string) => call<FeedReport>(`/runs/${encodeURIComponent(feedId)}`),
  setSource: (json: { url: string; format: string; mode: string }) =>
    call<{ source: FeedSource }>("/feeds/source", { method: "PUT", json }),
  removeSource: () => call<{ source: null }>("/feeds/source", { method: "DELETE" }),
  pullSource: () => call<{ source: FeedSource }>("/feeds/source/pull", { method: "POST" }),

  inbox: (filter: string) => {
    const qs = filter === "open" ? "?open=true" : filter === "all" ? "" : `?kind=${filter}`;
    return call<{ items: InboxItem[]; open: { requests: number; orders: number } }>(`/inbox${qs}`);
  },
  inboxItem: (id: string) => call<InboxItem>(`/inbox/${encodeURIComponent(id)}`),
  quote: (id: string, json: Record<string, unknown>) =>
    call<InboxItem>(`/inbox/${encodeURIComponent(id)}/quote`, { method: "POST", json }),
  ship: (id: string, carrier: string, reference: string) =>
    call<InboxItem>(`/inbox/${encodeURIComponent(id)}/ship`, { method: "POST", json: { carrier, reference } }),
  inboxAction: (id: string, action: "accept" | "reject" | "decline" | "deliver", reason?: string) =>
    call<InboxItem>(`/inbox/${encodeURIComponent(id)}/${action}`, { method: "POST", json: reason ? { reason } : {} }),

  analytics: (from: string, to: string, region: string) => {
    const p = new URLSearchParams({ from, to });
    if (region) p.set("region", region);
    return call<Analytics>(`/analytics?${p.toString()}`);
  },

  listing: () => call<ListingView>("/listing"),
  chooseListing: (plan: string) =>
    call<{ state: string; plan: string; checkout_url: string | null; detail?: string; listing: ListingView }>("/listing", {
      method: "POST",
      json: { plan },
    }),
  statements: () => call<Statements>("/statements"),
  invoice: (id: string) => call<{ url: string }>(`/statements/${encodeURIComponent(id)}/invoice`),
  connectPayouts: () => call<{ url: string }>("/payouts/connect", { method: "POST" }),

  team: () => call<Team>("/members"),
  invite: (email: string, role: Role) => call<{ invite_id: string }>("/members", { method: "POST", json: { email, role } }),
  setRole: (userId: number, role: Role) => call<Team>(`/members/${userId}`, { method: "PATCH", json: { role } }),
  removeMember: (userId: number) => call<Team>(`/members/${userId}`, { method: "DELETE" }),
  revokeInvite: (id: string) => call<Team>(`/invites/${encodeURIComponent(id)}`, { method: "DELETE" }),
  acceptInvite: (token: string) =>
    call<{ supplier_id: string; role: Role; name?: string }>("/invites/accept", { method: "POST", json: { token } }),
  createKey: (name: string) => call<Team["keys"][number] & { key: string }>("/keys", { method: "POST", json: { name } }),
  revokeKey: (id: number) => call<Team["keys"][number]>(`/keys/${id}`, { method: "DELETE" }),
};

/** Public catalogue reads the portal's forms use (contract 5.1, 5.2). */
export const marketReads = {
  categories: () => api<{ categories: Category[] }>("/market/categories", { headers: CONTRACT, auth: false }),
  regions: () => api<{ regions: MarketRegion[] }>("/market/regions", { headers: CONTRACT, auth: false }),
};

/** Download the XLSX template (a file, so not through api()). */
export async function downloadTemplate(): Promise<void> {
  const h = headers();
  const token = getToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/supplier/imports/template.xlsx`, { headers: h });
  } catch {
    throw new ApiError(0, "Can't reach the Truebex server. Please try again in a moment.");
  }
  if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "truebex-catalogue-template.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "1299.00" from 129900 and the exponent (display and form values). */
export function toMajor(amount: number, exponent: number): string {
  if (exponent === 0) return String(amount);
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount);
  const scale = 10 ** exponent;
  return `${sign}${Math.floor(abs / scale)}.${String(abs % scale).padStart(exponent, "0")}`;
}

/** Fill "{name}" placeholders of a constants string. */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}

/** "6 rows · 6 created · …" for a dry run or a run's report. */
export function countsLine(
  template: string,
  r: { rows: number; created: number; updated: number; unchanged: number; rejected: number }
): string {
  return fill(template, { rows: r.rows, created: r.created, updated: r.updated, unchanged: r.unchanged, rejected: r.rejected });
}

/** 482113 → "471 KB"; 900 → "900 bytes". */
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} bytes`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
