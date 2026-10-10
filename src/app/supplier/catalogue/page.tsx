"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, can, Field, inputClass, OkNote, productTone, useMember } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import { fill, marketReads, supplierApi, type Category, type ProductSummary } from "@/lib/supplier";
import { cn } from "@/lib/utils";

const C = SUPPLIER.catalogue;
const FILTERS = ["all", "draft", "pending_review", "approved", "rejected", "hidden", "withdrawn"];

// Products with their state badges; a draft is created here and edited on
// /supplier/catalogue/product/?id=.
export default function CataloguePage() {
  const { me, role } = useMember();
  const router = useRouter();
  const editor = can(role, "catalogue");
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ProductSummary[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ sku: "", name: "", kind: "object", category: "", description: "", brand: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (s: string, query: string) => {
    try {
      const res = await supplierApi.products(s, query);
      setItems(res.products);
      setCounts(res.counts);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(status, q), q ? 250 : 0);
    return () => clearTimeout(t);
  }, [status, q, load]);

  useEffect(() => {
    if (showNew && categories.length === 0) {
      marketReads
        .categories()
        .then((r) => setCategories(r.categories))
        .catch(() => setCategories([]));
    }
  }, [showNew, categories.length]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const made = await supplierApi.createProduct({
        sku: form.sku,
        name: form.name,
        kind: form.kind,
        category: form.category,
        description: form.description,
        brand: form.brand || null,
      });
      router.push(`/supplier/catalogue/product/?id=${made.product_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  async function submitDrafts() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const res = await supplierApi.submitDrafts();
      const parts = [fill(C.submitted, { n: res.submitted.length })];
      if (res.skipped.length)
        parts.push(fill(C.skipped, { n: res.skipped.length, skus: res.skipped.map((s) => `${s.sku} (${s.missing.join(", ")})`).join("; ") }));
      setNote(parts.join(" "));
      await load(status, q);
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  const drafts = (counts.draft ?? 0) + (counts.rejected ?? 0);
  return (
    <>
      <PageHeader
        title={C.title}
        description={C.description}
        actions={
          editor ? (
            <div className="flex flex-wrap gap-2">
              {drafts > 0 && me.supplier?.status === "verified" && (
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => void submitDrafts()}>
                  {C.submitDrafts}
                </Button>
              )}
              <Button size="sm" onClick={() => setShowNew((v) => !v)}>
                {C.newProduct}
              </Button>
            </div>
          ) : undefined
        }
      />
      <div className="space-y-4">
        {error && <ErrorNote message={error} />}
        {note && <OkNote message={note} />}
        {showNew && editor && (
          <Panel>
            <form onSubmit={create} className="grid gap-4 sm:grid-cols-2">
              <Field label={C.sku}>
                <input required maxLength={64} value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className={inputClass} />
              </Field>
              <Field label={C.name}>
                <input required maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} />
              </Field>
              <Field label={C.kind}>
                <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className={inputClass}>
                  {Object.entries(C.kinds).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={C.category}>
                <select required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={inputClass}>
                  <option value="" />
                  {categories.map((c) => (
                    <option key={c.path} value={c.path}>
                      {c.path}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={C.descriptionLabel} className="sm:col-span-2">
                <textarea maxLength={2000} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className={inputClass} />
              </Field>
              <Field label={C.brand}>
                <input maxLength={70} value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className={inputClass} />
              </Field>
              <div className="flex items-end">
                <Button type="submit" disabled={busy}>
                  {C.create}
                </Button>
              </div>
            </form>
          </Panel>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0">
            {FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setStatus(f)}
                className={cn(
                  "whitespace-nowrap rounded-full border px-3 py-1 text-xs",
                  f === status ? "border-accent bg-accent/10 text-accent" : "border-border text-text-secondary hover:text-text-primary"
                )}
              >
                {SUPPLIER.productStatus[f] ?? f}
                {f !== "all" && counts[f] ? ` (${counts[f]})` : ""}
              </button>
            ))}
          </div>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={C.search}
            aria-label={C.search}
            className={cn(inputClass, "sm:w-64")}
          />
        </div>

        {items && items.length === 0 && (
          <Panel>
            <p className="text-text-secondary">{C.empty}</p>
          </Panel>
        )}
        <ul className="space-y-3">
          {items?.map((p) => (
            <li key={p.product_id}>
              <Link
                href={`/supplier/catalogue/product/?id=${p.product_id}`}
                className="flex gap-4 rounded-[var(--radius-card)] border border-border bg-surface p-3 transition-colors hover:border-accent/50 md:p-4"
              >
                {p.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- API-served thumbnail, static export
                  <img src={p.thumbnail_url} alt={p.name} width={64} height={64} className="h-16 w-16 shrink-0 rounded object-cover" />
                ) : (
                  <div className="h-16 w-16 shrink-0 rounded bg-white/5" aria-hidden />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-semibold text-text-primary">{p.name}</p>
                    <Badge tone={productTone(p.status)}>{SUPPLIER.productStatus[p.status] ?? p.status}</Badge>
                  </div>
                  <p className="truncate text-sm text-text-muted">
                    {p.sku} · {p.category} · {p.variants} {C.variants}
                  </p>
                  {p.review_note && <p className="mt-1 text-xs text-warn">{p.review_note}</p>}
                  <p className="mt-1 text-xs text-text-muted">{formatDate(p.updated_at)}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
