"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, can, Field, inputClass, OkNote, productTone, useMember } from "@/components/supplier/SupplierShell";
import { SUPPLIER } from "@/lib/constants";
import { marketReads, supplierApi, type Category, type ProductFull, type Variant } from "@/lib/supplier";

const P = SUPPLIER.product;
const C = SUPPLIER.catalogue;

function useAct(onDone: (p: ProductFull) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (fn: () => Promise<ProductFull | unknown>) => {
    setBusy(true);
    setError("");
    try {
      const out = await fn();
      if (out && typeof out === "object" && "product_id" in (out as object)) onDone(out as ProductFull);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      return false;
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, act, setError };
}

function VariantCard({
  product,
  v,
  editable,
  onChange,
}: {
  product: ProductFull;
  v: Variant;
  editable: boolean;
  onChange: (p: ProductFull) => void;
}) {
  const { busy, error, act } = useAct(onChange);
  const [checkNote, setCheckNote] = useState<string[]>([]);
  const g = v.geometry;
  const opts = Object.values(v.options).filter(Boolean).join(" · ");

  async function uploadGeometry(file: File) {
    const ok = await act(async () => {
      const res = await supplierApi.uploadGeometry(product.product_id, v.variant_id, file);
      setCheckNote((res.check?.warnings ?? []).map((w) => w.detail));
      return supplierApi.product(product.product_id);
    });
    if (!ok) setCheckNote([]);
  }

  return (
    <Panel className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-text-primary">
            {v.variant_id}
            {opts && <span className="ml-2 text-sm font-normal text-text-muted">{opts}</span>}
          </p>
          <p className="text-sm text-text-muted">
            {v.dims_mm ? `${v.dims_mm.join(" × ")} mm` : "—"}
            {v.materials.length ? ` · ${v.materials.join(", ")}` : ""}
            {v.gtin ? ` · GTIN ${v.gtin}` : ""}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {v.regions.length ? `${P.pricedIn} ${v.regions.join(", ")}` : P.notPriced} ·{" "}
            <Link href="/supplier/prices/" className="text-accent hover:underline">
              {P.editPrices}
            </Link>
          </p>
        </div>
        <Badge tone={v.status === "active" ? "neutral" : "warn"}>{P.variantStatus[v.status] ?? v.status}</Badge>
      </div>

      <div>
        <h3 className="text-sm font-semibold">{P.pictures}</h3>
        <p className="text-xs text-text-muted">{P.picturesHelp}</p>
        <div className="mt-2 flex flex-wrap gap-3">
          {v.images.map((img) => (
            <figure key={img.sha256} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element -- API-served picture, static export */}
              <img src={img.thumb_url} alt={`${product.name} ${v.variant_id}`} width={96} height={96} className="h-24 w-24 rounded object-cover" />
              {editable && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void act(() => supplierApi.removeImage(product.product_id, v.variant_id, img.sha256))}
                  className="mt-1 block text-xs text-red-300 hover:underline"
                >
                  {P.remove}
                </button>
              )}
            </figure>
          ))}
        </div>
        {editable && (
          <label className="mt-2 inline-block cursor-pointer text-sm text-accent hover:underline">
            {P.addPicture}
            <input
              type="file"
              accept="image/jpeg,image/png"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) void act(() => supplierApi.addImage(product.product_id, v.variant_id, f));
              }}
            />
          </label>
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold">{P.geometry}</h3>
        <p className="text-xs text-text-muted">{P.geometryHelp}</p>
        {g ? (
          <p className="mt-2 text-sm text-text-secondary">
            {g.format.toUpperCase()} · {(g.bytes / 1024).toFixed(0)} KB · rev {g.rev ?? 1}
            {g.check?.triangles != null && ` · ${g.check.triangles.toLocaleString("en-US")} ${P.triangles}`}
            {g.check?.measured_mm && ` · ${P.measured} ${g.check.measured_mm.join(" × ")} mm`}
          </p>
        ) : (
          <p className="mt-2 text-sm text-text-muted">{P.noGeometry}</p>
        )}
        {(checkNote.length ? checkNote : (g?.check?.warnings ?? []).map((w) => w.detail)).map((w) => (
          <p key={w} className="mt-1 text-xs text-warn">
            {w}
          </p>
        ))}
        {editable && (
          <label className="mt-2 inline-block cursor-pointer text-sm text-accent hover:underline">
            {busy ? P.uploading : P.uploadGeometry}
            <input
              type="file"
              accept=".glb,.gltf,.fbx,.obj,.tbxa"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) void uploadGeometry(f);
              }}
            />
          </label>
        )}
      </div>

      {editable && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (window.confirm(P.confirmRemoveVariant)) void act(() => supplierApi.removeVariant(product.product_id, v.variant_id));
          }}
          className="text-xs text-red-300 hover:underline"
        >
          {P.removeVariant}
        </button>
      )}
      {error && <ErrorNote message={error} />}
    </Panel>
  );
}

function AddVariant({ product, onChange }: { product: ProductFull; onChange: (p: ProductFull) => void }) {
  const { busy, error, act } = useAct(onChange);
  const empty = { variant_id: product.variants.length ? "" : "default", size: "", colour: "", finish: "", w: "", h: "", d: "", materials: "", gtin: "" };
  const [f, setF] = useState(empty);
  const set = (k: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const dims = [f.w, f.h, f.d].every((x) => /^\d+$/.test(x)) ? [Number(f.w), Number(f.h), Number(f.d)] : null;

  return (
    <Panel>
      <h3 className="font-semibold">{P.addVariant}</h3>
      <form
        className="mt-3 grid gap-3 sm:grid-cols-3"
        onSubmit={async (e) => {
          e.preventDefault();
          const ok = await act(() =>
            supplierApi.addVariant(product.product_id, {
              variant_id: f.variant_id || "default",
              options: { size: f.size || null, colour: f.colour || null, finish: f.finish || null },
              dims_mm: dims,
              materials: f.materials.split(";").map((m) => m.trim()).filter(Boolean),
              gtin: f.gtin || null,
            })
          );
          if (ok) setF({ ...empty, variant_id: "" });
        }}
      >
        <Field label={P.variantId} className="sm:col-span-3">
          <input required maxLength={64} value={f.variant_id} onChange={set("variant_id")} className={inputClass} />
        </Field>
        <Field label={P.size}>
          <input maxLength={40} value={f.size} onChange={set("size")} className={inputClass} />
        </Field>
        <Field label={P.colour}>
          <input maxLength={40} value={f.colour} onChange={set("colour")} className={inputClass} />
        </Field>
        <Field label={P.finish}>
          <input maxLength={40} value={f.finish} onChange={set("finish")} className={inputClass} />
        </Field>
        <fieldset className="grid grid-cols-3 gap-2 sm:col-span-3">
          <legend className="mb-1 text-sm text-text-secondary">{P.dims}</legend>
          <input inputMode="numeric" aria-label={P.width} placeholder={P.width} value={f.w} onChange={set("w")} className={inputClass} />
          <input inputMode="numeric" aria-label={P.height} placeholder={P.height} value={f.h} onChange={set("h")} className={inputClass} />
          <input inputMode="numeric" aria-label={P.depth} placeholder={P.depth} value={f.d} onChange={set("d")} className={inputClass} />
        </fieldset>
        <Field label={P.materials} className="sm:col-span-2">
          <input value={f.materials} onChange={set("materials")} className={inputClass} placeholder="linen;oak" />
        </Field>
        <Field label={P.gtin}>
          <input inputMode="numeric" maxLength={14} value={f.gtin} onChange={set("gtin")} className={inputClass} />
        </Field>
        <div className="sm:col-span-3">
          <Button type="submit" disabled={busy}>
            {P.addVariant}
          </Button>
        </div>
      </form>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
    </Panel>
  );
}

function ProductEditor() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  const { role } = useMember();
  const editor = can(role, "catalogue");
  const [product, setProduct] = useState<ProductFull | null>(null);
  const [loadError, setLoadError] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ name: "", kind: "object", category: "", description: "", brand: "" });
  const [saved, setSaved] = useState("");

  const show = useCallback((p: ProductFull) => {
    setProduct(p);
    setForm({ name: p.name, kind: p.kind, category: p.category, description: p.description, brand: p.brand ?? "" });
  }, []);
  const { busy, error, act } = useAct(show);

  useEffect(() => {
    if (!id) return;
    supplierApi
      .product(id)
      .then(show)
      .catch((err) => setLoadError(err instanceof Error ? err.message : SUPPLIER.errors.generic));
    marketReads
      .categories()
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]));
  }, [id, show]);

  if (!id) return <p className="text-text-secondary">{P.missing}</p>;
  if (loadError) return <ErrorNote message={loadError} />;
  if (!product) return <p className="text-text-muted" role="status">{P.loading}</p>;

  const editable = editor && product.editable;
  const doAction = (action: "submit" | "hide" | "show" | "withdraw" | "discontinue", confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    void act(() => supplierApi.productAction(product.product_id, action));
  };

  return (
    <>
      <Link href="/supplier/catalogue/" className="text-sm text-accent hover:underline">
        ← {P.back}
      </Link>
      <div className="mt-4">
        <PageHeader
          title={product.name}
          description={`${product.sku} · ${product.category}${product.app_path && product.app_path !== product.category ? ` → ${product.app_path}` : ""}`}
          actions={<Badge tone={productTone(product.status)}>{SUPPLIER.productStatus[product.status] ?? product.status}</Badge>}
        />
      </div>
      <div className="space-y-6">
        {product.review_note && (
          <div className="rounded-[var(--radius-card)] border border-warn/30 bg-warn/5 p-4 text-sm text-warn">
            <strong>{P.reviewNote}:</strong> {product.review_note}
          </div>
        )}
        {error && <ErrorNote message={error} />}
        {saved && <OkNote message={saved} />}

        {editor && (
          <div className="flex flex-wrap gap-2">
            {(product.status === "draft" || product.status === "rejected") && (
              <Button size="sm" disabled={busy} onClick={() => doAction("submit")}>
                {P.submit}
              </Button>
            )}
            {product.status === "approved" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => doAction("hide")}>
                {P.hide}
              </Button>
            )}
            {product.status === "hidden" && (
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => doAction("show")}>
                {P.show}
              </Button>
            )}
            {product.status !== "withdrawn" && (
              <>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => doAction("discontinue", P.confirmDiscontinue)}>
                  {P.discontinue}
                </Button>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => doAction("withdraw", P.confirmWithdraw)}>
                  {P.withdraw}
                </Button>
              </>
            )}
          </div>
        )}

        <Panel>
          <h2 className="font-semibold">{P.details}</h2>
          {product.status === "approved" && editable && <p className="mt-1 text-xs text-text-muted">{P.reReview}</p>}
          <form
            className="mt-4 grid gap-4 sm:grid-cols-2"
            onSubmit={async (e) => {
              e.preventDefault();
              setSaved("");
              const ok = await act(() =>
                supplierApi.editProduct(product.product_id, {
                  name: form.name,
                  kind: form.kind,
                  category: form.category,
                  description: form.description,
                  brand: form.brand || null,
                })
              );
              if (ok) setSaved(P.saved);
            }}
          >
            <Field label={C.name}>
              <input required disabled={!editable} maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} />
            </Field>
            <Field label={C.kind}>
              <select disabled={!editable} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className={inputClass}>
                {Object.entries(C.kinds).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={C.category} className="sm:col-span-2">
              <select disabled={!editable} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={inputClass}>
                {!categories.some((c) => c.path === form.category) && <option value={form.category}>{form.category}</option>}
                {categories.map((c) => (
                  <option key={c.path} value={c.path}>
                    {c.path}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={C.descriptionLabel} className="sm:col-span-2">
              <textarea disabled={!editable} maxLength={2000} rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className={inputClass} />
            </Field>
            <Field label={C.brand}>
              <input disabled={!editable} maxLength={70} value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className={inputClass} />
            </Field>
            {editable && (
              <div className="flex items-end">
                <Button type="submit" disabled={busy}>
                  {P.save}
                </Button>
              </div>
            )}
          </form>
        </Panel>

        <section className="space-y-4">
          <h2 className="text-lg font-semibold">{P.variants}</h2>
          {product.variants.map((v) => (
            <VariantCard key={v.variant_id} product={product} v={v} editable={editable} onChange={show} />
          ))}
          {editable && <AddVariant product={product} onChange={show} />}
        </section>
      </div>
    </>
  );
}

export default function ProductPage() {
  return (
    <Suspense fallback={<p className="text-text-muted">{P.loading}</p>}>
      <ProductEditor />
    </Suspense>
  );
}
