"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, can, Field, inputClass, OkNote, useMember } from "@/components/supplier/SupplierShell";
import { SUPPLIER } from "@/lib/constants";
import {
  fill,
  supplierApi,
  toMajor,
  type PriceGrid,
  type PriceRow,
  type PriceRowIn,
  type RegionSetting,
} from "@/lib/supplier";
import { cn } from "@/lib/utils";

const T = SUPPLIER.prices;
const STATUSES = ["active", "discontinued", "hidden"] as const;
const OVERRIDES = ["", "in_stock", "low_stock", "made_to_order", "out_of_stock"] as const;

// What a row shows and saves; strings as typed (money stays decimal text).
interface Cells {
  price: string;
  price_includes_tax: boolean;
  tax_rate_percent: string;
  delivery_fee: string;
  delivery_days_min: string;
  delivery_days_max: string;
  stock: string;
  lead_time_days: string;
  availability: string;
  status: string;
}

const keyOf = (r: PriceRow) => `${r.sku}\u0000${r.variant_id}`;
const str = (v: string | number | null | undefined) => (v === null || v === undefined ? "" : String(v));

function cellsOf(r: PriceRow): Cells {
  return {
    price: str(r.price),
    price_includes_tax: r.price_includes_tax,
    tax_rate_percent: str(r.tax_rate_percent),
    delivery_fee: str(r.delivery_fee),
    delivery_days_min: str(r.delivery_days_min),
    delivery_days_max: str(r.delivery_days_max),
    stock: str(r.stock),
    lead_time_days: str(r.lead_time_days),
    // Only low stock cannot be worked out from the stock: keep it.
    availability: r.availability === "low_stock" ? "low_stock" : "",
    status: !r.sold ? "hidden" : r.availability === "discontinued" ? "discontinued" : "active",
  };
}

function toRow(r: PriceRow, c: Cells): Partial<PriceRowIn> {
  return {
    sku: r.sku,
    variant_id: r.variant_id,
    // A row taken out of the region still names a price (the feed's rule).
    price: c.price || (c.status === "hidden" ? "0" : ""),
    price_includes_tax: c.price_includes_tax ? "true" : "false",
    tax_rate_percent: c.tax_rate_percent,
    delivery_fee: c.delivery_fee,
    delivery_days_min: c.delivery_days_min,
    delivery_days_max: c.delivery_days_max,
    stock: c.stock,
    lead_time_days: c.lead_time_days,
    availability: c.status === "active" ? c.availability : "",
    status: c.status,
  };
}

function RegionsPanel({ onSaved, editable }: { onSaved: () => void; editable: boolean }) {
  const [regions, setRegions] = useState<RegionSetting[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    supplierApi
      .regions()
      .then((r) => setRegions(r.regions))
      .catch((err) => setError(err instanceof Error ? err.message : SUPPLIER.errors.generic));
  }, []);

  if (!regions) return error ? <ErrorNote message={error} /> : null;
  const update = (code: string, patch: Partial<RegionSetting>) =>
    setRegions(regions.map((r) => (r.region === code ? { ...r, ...patch } : r)));

  async function save() {
    if (!regions) return;
    setBusy(true);
    setError("");
    setOk("");
    try {
      const res = await supplierApi.saveRegions(
        regions.map((r) => ({
          region: r.region,
          active: r.served,
          default_delivery_fee: r.default_delivery_fee || null,
          delivery_days_min: r.delivery_days_min,
          delivery_days_max: r.delivery_days_max,
        }))
      );
      setRegions(res.regions);
      setOk(SUPPLIER.product.saved);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  const days = (v: string) => (v === "" ? null : Math.max(0, Math.min(365, Math.trunc(Number(v)) || 0)));
  return (
    <Panel>
      <h2 className="font-semibold">{T.regionsTitle}</h2>
      <p className="mt-1 text-sm text-text-muted">{T.regionsHelp}</p>
      <ul className="mt-4 space-y-3">
        {regions.map((r) => (
          <li key={r.region} className="grid gap-3 rounded-[var(--radius-button)] border border-border p-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
            <label className="flex items-center gap-3 text-sm">
              <input type="checkbox" disabled={!editable} checked={r.served} onChange={(e) => update(r.region, { served: e.target.checked })} />
              <span>
                {r.name} <span className="text-text-muted">({r.region}, {r.currency})</span>
              </span>
            </label>
            <Field label={`${T.defaultFee} (${r.currency})`}>
              <input
                disabled={!editable}
                inputMode="decimal"
                value={r.default_delivery_fee ?? ""}
                onChange={(e) => update(r.region, { default_delivery_fee: e.target.value })}
                className={cn(inputClass, "sm:w-28")}
              />
            </Field>
            <Field label={T.daysMin}>
              <input
                disabled={!editable}
                inputMode="numeric"
                value={str(r.delivery_days_min)}
                onChange={(e) => update(r.region, { delivery_days_min: days(e.target.value) })}
                className={cn(inputClass, "sm:w-20")}
              />
            </Field>
            <Field label={T.daysMax}>
              <input
                disabled={!editable}
                inputMode="numeric"
                value={str(r.delivery_days_max)}
                onChange={(e) => update(r.region, { delivery_days_max: days(e.target.value) })}
                className={cn(inputClass, "sm:w-20")}
              />
            </Field>
          </li>
        ))}
      </ul>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      {ok && <div className="mt-3"><OkNote message={ok} /></div>}
      {editable && (
        <Button className="mt-4" size="sm" disabled={busy} onClick={() => void save()}>
          {T.saveRegions}
        </Button>
      )}
    </Panel>
  );
}

function PricesInner() {
  const { role, reload: reloadMe } = useMember();
  const editable = can(role, "catalogue");
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [grid, setGrid] = useState<PriceGrid | null>(null);
  const [loadError, setLoadError] = useState("");
  const [edits, setEdits] = useState<Record<string, Cells>>({});
  const [errors, setErrors] = useState<Record<string, Record<string, string>>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [bulk, setBulk] = useState({ stock: "", status: "active", pct: "" });
  const region = params.get("region") ?? "";

  const load = useCallback(async (code: string) => {
    try {
      const res = await supplierApi.prices(code || undefined);
      setGrid(res);
      setLoadError("");
    } catch (err) {
      setGrid(null);
      setLoadError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    supplierApi
      .prices(region || undefined)
      .then((res) => {
        if (cancelled) return;
        setGrid(res);
        setLoadError("");
        setEdits({});
        setErrors({});
        setSelected(new Set());
      })
      .catch((err) => {
        if (cancelled) return;
        setGrid(null);
        setLoadError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, [region]);

  const rows = useMemo(() => grid?.rows ?? [], [grid]);
  const current = (r: PriceRow) => edits[keyOf(r)] ?? cellsOf(r);
  const change = (r: PriceRow, patch: Partial<Cells>) => setEdits((e) => ({ ...e, [keyOf(r)]: { ...(e[keyOf(r)] ?? cellsOf(r)), ...patch } }));
  const dirty = Object.keys(edits);
  const exponent = grid?.region.exponent ?? 2;

  function applyBulk(kind: "stock" | "status" | "pct") {
    for (const r of rows) {
      if (!selected.has(keyOf(r))) continue;
      if (kind === "stock") change(r, { stock: bulk.stock });
      if (kind === "status") change(r, { status: bulk.status });
      if (kind === "pct" && r.amount !== null) {
        const pct = Number(bulk.pct);
        if (!Number.isFinite(pct)) continue;
        // On integer minor units, rounded to a whole unit of the currency's smallest coin.
        change(r, { price: toMajor(Math.max(0, Math.round(r.amount * (1 + pct / 100))), exponent) });
      }
    }
  }

  async function save() {
    if (!grid) return;
    const sent = rows.filter((r) => edits[keyOf(r)]);
    setBusy(true);
    setError("");
    setOk("");
    setErrors({});
    const res = await supplierApi.savePrices(grid.region.region, sent.map((r) => toRow(r, edits[keyOf(r)])));
    setBusy(false);
    if (res.ok) {
      setGrid(res.data);
      setEdits({});
      setSelected(new Set());
      setOk(fill(T.saved, { n: res.data.saved }));
      return;
    }
    setError(res.code === "rows_invalid" ? T.invalid : res.error);
    const map: Record<string, Record<string, string>> = {};
    for (const e of res.data?.errors ?? []) {
      const r = sent[e.row - 1];
      if (!r) continue;
      (map[keyOf(r)] ??= {})[e.column] = e.code;
    }
    setErrors(map);
  }

  const setRegion = (code: string) => router.replace(`${pathname}?region=${encodeURIComponent(code)}`);
  const cellError = (r: PriceRow, col: string) => errors[keyOf(r)]?.[col];
  const errClass = (r: PriceRow, col: string) => (cellError(r, col) ? "border-red-500/60" : "");
  const codeText = (code: string | undefined) => (code ? SUPPLIER.imports.codes[code] ?? code : "");

  const input = (r: PriceRow, col: keyof Cells, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <input
      {...props}
      disabled={!editable}
      value={String(current(r)[col])}
      onChange={(e) => change(r, { [col]: e.target.value } as Partial<Cells>)}
      aria-invalid={cellError(r, col) ? true : undefined}
      title={codeText(cellError(r, col))}
      className={cn(inputClass, "px-2 py-1.5", errClass(r, col), props.className)}
    />
  );

  return (
    <>
      <PageHeader title={T.title} description={T.description} />
      <div className="space-y-6">
        {loadError && (
          <ErrorNote message={grid === null && !region ? T.noRegion : loadError} />
        )}
        {grid && (
          <>
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0" role="tablist" aria-label={T.region}>
              {grid.served.map((code) => (
                <button
                  key={code}
                  type="button"
                  role="tab"
                  aria-selected={code === grid.region.region}
                  onClick={() => setRegion(code)}
                  className={cn(
                    "whitespace-nowrap rounded-full border px-4 py-1.5 text-sm",
                    code === grid.region.region ? "border-accent bg-accent/10 text-accent" : "border-border text-text-secondary"
                  )}
                >
                  {code}
                </button>
              ))}
            </div>
            <p className="text-sm text-text-muted">
              {grid.region.name} · {grid.region.currency} · {grid.region.tax.name} {grid.region.tax.rate_bp / 100} %
              {grid.region.tax.prices_include_tax ? ` · ${T.inclTax}` : ""}
            </p>

            {rows.length === 0 && (
              <Panel>
                <p className="text-text-secondary">{T.empty}</p>
              </Panel>
            )}

            {editable && rows.length > 0 && (
              <div className="flex flex-wrap items-end gap-3 rounded-[var(--radius-card)] border border-border bg-surface p-3 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selected.size === rows.length}
                    onChange={(e) => setSelected(e.target.checked ? new Set(rows.map(keyOf)) : new Set())}
                  />
                  {T.selectAll} ({selected.size})
                </label>
                <div className="flex items-end gap-1">
                  <input inputMode="numeric" placeholder={T.setStock} aria-label={T.setStock} value={bulk.stock} onChange={(e) => setBulk({ ...bulk, stock: e.target.value })} className={cn(inputClass, "w-28 px-2 py-1.5")} />
                  <Button size="sm" variant="ghost" disabled={!selected.size} onClick={() => applyBulk("stock")}>
                    {T.apply}
                  </Button>
                </div>
                <div className="flex items-end gap-1">
                  <select aria-label={T.status} value={bulk.status} onChange={(e) => setBulk({ ...bulk, status: e.target.value })} className={cn(inputClass, "w-36 px-2 py-1.5")}>
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {T.statuses[s]}
                      </option>
                    ))}
                  </select>
                  <Button size="sm" variant="ghost" disabled={!selected.size} onClick={() => applyBulk("status")}>
                    {T.apply}
                  </Button>
                </div>
                <div className="flex items-end gap-1">
                  <input inputMode="decimal" placeholder={T.adjust} aria-label={T.adjust} value={bulk.pct} onChange={(e) => setBulk({ ...bulk, pct: e.target.value })} className={cn(inputClass, "w-40 px-2 py-1.5")} />
                  <Button size="sm" variant="ghost" disabled={!selected.size || !bulk.pct} onClick={() => applyBulk("pct")}>
                    {T.apply}
                  </Button>
                </div>
              </div>
            )}

            {/* Phones: one card per variant with price, stock and state first. */}
            <ul className="space-y-3 md:hidden">
              {rows.map((r) => {
                const c = current(r);
                return (
                  <li key={keyOf(r)} className={cn("rounded-[var(--radius-card)] border bg-surface p-4", edits[keyOf(r)] ? "border-accent/60" : "border-border")}>
                    <div className="flex items-start gap-3">
                      {editable && (
                        <input
                          type="checkbox"
                          aria-label={`${r.sku} ${r.variant_id}`}
                          checked={selected.has(keyOf(r))}
                          onChange={(e) => {
                            const next = new Set(selected);
                            if (e.target.checked) next.add(keyOf(r));
                            else next.delete(keyOf(r));
                            setSelected(next);
                          }}
                          className="mt-1"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-semibold text-text-primary">{r.name}</p>
                        <p className="truncate text-xs text-text-muted">
                          {r.sku} · {r.variant_id}
                          {Object.values(r.options).length ? ` · ${Object.values(r.options).join(" · ")}` : ""}
                        </p>
                      </div>
                      <Badge tone={c.status === "active" ? "good" : c.status === "hidden" ? "neutral" : "warn"}>{T.statuses[c.status]}</Badge>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <Field label={`${T.price} (${grid.region.currency})`}>{input(r, "price", { inputMode: "decimal" })}</Field>
                      <Field label={T.stock}>{input(r, "stock", { inputMode: "numeric" })}</Field>
                      <Field label={T.status}>
                        <select disabled={!editable} value={c.status} onChange={(e) => change(r, { status: e.target.value })} className={cn(inputClass, "px-2 py-1.5")}>
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {T.statuses[s]}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label={T.availability}>
                        <select disabled={!editable} value={c.availability} onChange={(e) => change(r, { availability: e.target.value })} className={cn(inputClass, "px-2 py-1.5", errClass(r, "availability"))}>
                          {OVERRIDES.map((s) => (
                            <option key={s} value={s}>
                              {T.availabilityStates[s]}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                    <details className="mt-3 text-sm">
                      <summary className="cursor-pointer text-text-muted">
                        {T.deliveryFee}, {T.taxRate}, {T.leadTime}
                      </summary>
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        <Field label={T.deliveryFee}>{input(r, "delivery_fee", { inputMode: "decimal" })}</Field>
                        <Field label={T.taxRate}>{input(r, "tax_rate_percent", { inputMode: "decimal" })}</Field>
                        <Field label={T.daysMin}>{input(r, "delivery_days_min", { inputMode: "numeric" })}</Field>
                        <Field label={T.daysMax}>{input(r, "delivery_days_max", { inputMode: "numeric" })}</Field>
                        <Field label={T.leadTime}>{input(r, "lead_time_days", { inputMode: "numeric" })}</Field>
                        <label className="flex items-center gap-2 self-end text-text-secondary">
                          <input type="checkbox" disabled={!editable} checked={c.price_includes_tax} onChange={(e) => change(r, { price_includes_tax: e.target.checked })} />
                          {T.inclTax}
                        </label>
                      </div>
                    </details>
                    {errors[keyOf(r)] && (
                      <p className="mt-2 text-xs text-red-300">
                        {Object.entries(errors[keyOf(r)]).map(([col, code]) => `${col}: ${codeText(code)}`).join(" ")}
                      </p>
                    )}
                    {!r.sold && c.status === "hidden" && <p className="mt-2 text-xs text-text-muted">{T.notSold}</p>}
                  </li>
                );
              })}
            </ul>

            {/* Desktop: the grid. */}
            {rows.length > 0 && (
              <div className="hidden overflow-x-auto rounded-[var(--radius-card)] border border-border md:block">
                <table className="w-full text-sm">
                  <thead className="bg-surface-elevated text-left text-xs text-text-muted">
                    <tr>
                      {editable && <th className="px-2 py-2" />}
                      <th className="px-2 py-2 font-medium">{T.product}</th>
                      <th className="px-2 py-2 font-medium">{T.price} ({grid.region.currency})</th>
                      <th className="px-2 py-2 font-medium">{T.inclTax}</th>
                      <th className="px-2 py-2 font-medium">{T.taxRate}</th>
                      <th className="px-2 py-2 font-medium">{T.deliveryFee}</th>
                      <th className="px-2 py-2 font-medium">{T.days}</th>
                      <th className="px-2 py-2 font-medium">{T.stock}</th>
                      <th className="px-2 py-2 font-medium">{T.leadTime}</th>
                      <th className="px-2 py-2 font-medium">{T.availability}</th>
                      <th className="px-2 py-2 font-medium">{T.status}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const c = current(r);
                      return (
                        <tr key={keyOf(r)} className={cn("border-t border-border align-top", edits[keyOf(r)] && "bg-accent/5")}>
                          {editable && (
                            <td className="px-2 py-2">
                              <input
                                type="checkbox"
                                aria-label={`${r.sku} ${r.variant_id}`}
                                checked={selected.has(keyOf(r))}
                                onChange={(e) => {
                                  const next = new Set(selected);
                                  if (e.target.checked) next.add(keyOf(r));
                                  else next.delete(keyOf(r));
                                  setSelected(next);
                                }}
                              />
                            </td>
                          )}
                          <td className="max-w-[14rem] px-2 py-2">
                            <p className="truncate font-medium text-text-primary">{r.name}</p>
                            <p className="truncate text-xs text-text-muted">
                              {r.sku} · {r.variant_id}
                            </p>
                            {errors[keyOf(r)] && (
                              <p className="mt-1 text-xs text-red-300">
                                {Object.entries(errors[keyOf(r)]).map(([col, code]) => `${col}: ${codeText(code)}`).join(" ")}
                              </p>
                            )}
                          </td>
                          <td className="px-2 py-2">{input(r, "price", { inputMode: "decimal", className: "w-28" })}</td>
                          <td className="px-2 py-2 text-center">
                            <input type="checkbox" aria-label={T.inclTax} disabled={!editable} checked={c.price_includes_tax} onChange={(e) => change(r, { price_includes_tax: e.target.checked })} />
                          </td>
                          <td className="px-2 py-2">{input(r, "tax_rate_percent", { inputMode: "decimal", className: "w-16" })}</td>
                          <td className="px-2 py-2">{input(r, "delivery_fee", { inputMode: "decimal", className: "w-24" })}</td>
                          <td className="px-2 py-2">
                            <div className="flex gap-1">
                              {input(r, "delivery_days_min", { inputMode: "numeric", className: "w-14", "aria-label": T.daysMin })}
                              {input(r, "delivery_days_max", { inputMode: "numeric", className: "w-14", "aria-label": T.daysMax })}
                            </div>
                          </td>
                          <td className="px-2 py-2">{input(r, "stock", { inputMode: "numeric", className: "w-20" })}</td>
                          <td className="px-2 py-2">{input(r, "lead_time_days", { inputMode: "numeric", className: "w-16" })}</td>
                          <td className="px-2 py-2">
                            <select disabled={!editable} aria-label={T.availability} value={c.availability} onChange={(e) => change(r, { availability: e.target.value })} className={cn(inputClass, "w-36 px-2 py-1.5", errClass(r, "availability"))}>
                              {OVERRIDES.map((s) => (
                                <option key={s} value={s}>
                                  {T.availabilityStates[s]}
                                </option>
                              ))}
                            </select>
                            {r.availability && <p className="mt-1 text-xs text-text-muted">{T.availabilityStates[r.availability] ?? r.availability}</p>}
                          </td>
                          <td className="px-2 py-2">
                            <select disabled={!editable} aria-label={T.status} value={c.status} onChange={(e) => change(r, { status: e.target.value })} className={cn(inputClass, "w-32 px-2 py-1.5")}>
                              {STATUSES.map((s) => (
                                <option key={s} value={s}>
                                  {T.statuses[s]}
                                </option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {error && <ErrorNote message={error} />}
            {ok && <OkNote message={ok} />}
            {editable && dirty.length > 0 && (
              <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-accent/40 bg-surface-elevated p-3 shadow-lg">
                <span className="text-sm text-text-secondary">{fill(T.unsaved, { n: dirty.length })}</span>
                <Button size="sm" disabled={busy} onClick={() => void save()}>
                  {busy ? T.saving : T.save}
                </Button>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => { setEdits({}); setErrors({}); }}>
                  {T.discard}
                </Button>
              </div>
            )}
          </>
        )}
        <RegionsPanel
          editable={editable}
          onSaved={() => {
            void reloadMe();
            void load(region);
          }}
        />
      </div>
    </>
  );
}

export default function PricesPage() {
  return (
    <Suspense fallback={<p className="text-text-muted">…</p>}>
      <PricesInner />
    </Suspense>
  );
}
