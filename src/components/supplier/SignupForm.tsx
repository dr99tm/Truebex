"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ErrorNote } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, Field, inputClass, useSupplier } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import { marketReads, setSupplierId, supplierApi, type MarketRegion } from "@/lib/supplier";
import { useIsAuthenticated } from "@/lib/useAuth";
import { cn } from "@/lib/utils";

const S = SUPPLIER.signup;
const NEXT = encodeURIComponent("/supplier/signup/");

interface Form {
  name: string;
  legal_name: string;
  country: string;
  company_number: string;
  vat_id: string;
  website: string;
  line1: string;
  line2: string;
  city: string;
  postcode: string;
  address_country: string;
  regions: string[];
  contact_name: string;
  contact_email: string;
  contact_phone: string;
}

const EMPTY: Form = {
  name: "",
  legal_name: "",
  country: "",
  company_number: "",
  vat_id: "",
  website: "",
  line1: "",
  line2: "",
  city: "",
  postcode: "",
  address_country: "",
  regions: [],
  contact_name: "",
  contact_email: "",
  contact_phone: "",
};

function body(f: Form) {
  const opt = (v: string) => (v.trim() ? v.trim() : null);
  return {
    name: f.name,
    legal_name: f.legal_name,
    country: f.country.toUpperCase(),
    company_number: f.company_number,
    vat_id: opt(f.vat_id),
    website: opt(f.website),
    address: {
      line1: f.line1,
      line2: opt(f.line2),
      city: f.city,
      postcode: opt(f.postcode),
      country: (f.address_country || f.country).toUpperCase(),
    },
    regions: f.regions,
    contact: { name: f.contact_name, email: f.contact_email, phone: opt(f.contact_phone) },
  };
}

// The supplier application in three steps (company, regions and contact,
// document), then "Under review". An account that already applied sees its
// application's state instead.
export function SignupForm() {
  const authed = useIsAuthenticated();
  const { me, reload } = useSupplier();
  const [form, setForm] = useState<Form>(EMPTY);
  const [step, setStep] = useState(0);
  const [regions, setRegions] = useState<MarketRegion[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    marketReads
      .regions()
      .then((r) => setRegions(r.regions))
      .catch(() => setRegions([]));
  }, []);

  if (authed === null || (authed && !me)) return <p className="text-text-muted">{SUPPLIER.shell.loading}</p>;

  if (!authed) {
    return (
      <div className="space-y-4">
        <p className="text-text-secondary">{S.signedOut}</p>
        <div className="flex flex-wrap gap-3">
          <Button href={`/signup/?next=${NEXT}`}>{S.createAccount}</Button>
          <Button href={`/login/?next=${NEXT}`} variant="secondary">
            {S.signIn}
          </Button>
        </div>
      </div>
    );
  }

  const owned = me?.supplier && me.role === "owner" ? me : null;
  if (owned?.application || (me?.supplier && !owned)) {
    return <Applied />;
  }

  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const toggle = (code: string) =>
    setForm({ ...form, regions: form.regions.includes(code) ? form.regions.filter((r) => r !== code) : [...form.regions, code] });

  const stepValid = [
    form.name && form.legal_name && /^[A-Za-z]{2}$/.test(form.country) && form.company_number && form.line1 && form.city,
    form.regions.length > 0 && form.contact_name && form.contact_email.includes("@"),
    !!file,
  ];

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const app = await supplierApi.apply(body(form));
      setSupplierId(app.supplier_id);
      await supplierApi.uploadDocument(file);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      // The application may exist already (a failed upload): show its state.
      await reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (step < 2) setStep(step + 1);
        else void submit();
      }}
      className="space-y-6"
    >
      <ol className="flex flex-wrap gap-2 text-xs" aria-label="Steps">
        {S.steps.map((label, i) => (
          <li
            key={label}
            aria-current={i === step ? "step" : undefined}
            className={cn(
              "rounded-full border px-3 py-1",
              i === step ? "border-accent bg-accent/10 text-accent" : "border-border text-text-muted"
            )}
          >
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={S.company.name} hint={S.company.nameHint}>
            <input required value={form.name} onChange={set("name")} className={inputClass} maxLength={120} />
          </Field>
          <Field label={S.company.legalName}>
            <input required value={form.legal_name} onChange={set("legal_name")} className={inputClass} maxLength={200} />
          </Field>
          <Field label={S.company.country}>
            <input required value={form.country} onChange={set("country")} className={inputClass} maxLength={2} autoCapitalize="characters" />
          </Field>
          <Field label={S.company.companyNumber}>
            <input required value={form.company_number} onChange={set("company_number")} className={inputClass} maxLength={40} />
          </Field>
          <Field label={S.company.vatId}>
            <input value={form.vat_id} onChange={set("vat_id")} className={inputClass} maxLength={40} />
          </Field>
          <Field label={S.company.website}>
            <input type="url" value={form.website} onChange={set("website")} className={inputClass} placeholder="https://" />
          </Field>
          <Field label={S.company.line1} className="sm:col-span-2">
            <input required value={form.line1} onChange={set("line1")} className={inputClass} maxLength={200} />
          </Field>
          <Field label={S.company.line2} className="sm:col-span-2">
            <input value={form.line2} onChange={set("line2")} className={inputClass} maxLength={200} />
          </Field>
          <Field label={S.company.city}>
            <input required value={form.city} onChange={set("city")} className={inputClass} maxLength={120} />
          </Field>
          <Field label={S.company.postcode}>
            <input value={form.postcode} onChange={set("postcode")} className={inputClass} maxLength={20} />
          </Field>
          <Field label={S.company.addressCountry}>
            <input
              value={form.address_country}
              onChange={set("address_country")}
              placeholder={form.country}
              className={inputClass}
              maxLength={2}
            />
          </Field>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-6">
          <fieldset>
            <legend className="font-semibold">{S.regions.title}</legend>
            <p className="mt-1 text-sm text-text-muted">{S.regions.help}</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {regions.map((r) => (
                <label
                  key={r.region}
                  className="flex items-center gap-3 rounded-[var(--radius-button)] border border-border px-3 py-2 text-sm"
                >
                  <input type="checkbox" checked={form.regions.includes(r.region)} onChange={() => toggle(r.region)} />
                  <span>
                    {r.name} <span className="text-text-muted">({r.region}, {r.currency})</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="mb-2 font-semibold">{S.regions.contactTitle}</legend>
            <Field label={S.regions.contactName}>
              <input required value={form.contact_name} onChange={set("contact_name")} className={inputClass} maxLength={120} />
            </Field>
            <Field label={S.regions.contactEmail}>
              <input required type="email" value={form.contact_email} onChange={set("contact_email")} className={inputClass} />
            </Field>
            <Field label={S.regions.contactPhone}>
              <input type="tel" value={form.contact_phone} onChange={set("contact_phone")} className={inputClass} maxLength={40} />
            </Field>
          </fieldset>
        </div>
      )}

      {step === 2 && (
        <div>
          <h2 className="font-semibold">{S.document.title}</h2>
          <p className="mt-1 text-sm text-text-muted">{S.document.help}</p>
          <Field label={S.document.choose} className="mt-4">
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm text-text-secondary file:mr-3 file:rounded-[var(--radius-button)] file:border file:border-border file:bg-surface file:px-3 file:py-2 file:text-text-primary"
            />
          </Field>
        </div>
      )}

      {error && <ErrorNote message={error} />}

      <div className="flex flex-wrap gap-3">
        {step > 0 && (
          <Button type="button" variant="secondary" onClick={() => setStep(step - 1)}>
            {S.back}
          </Button>
        )}
        <Button type="submit" disabled={!stepValid[step] || busy}>
          {step < 2 ? S.next : busy ? S.sending : S.submit}
        </Button>
      </div>
    </form>
  );
}

/** The account's application: under review (with its documents), verified or declined. */
function Applied() {
  const { me, reload } = useSupplier();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const app = me?.application;
  const supplier = me?.supplier;
  if (!supplier) return null;
  const state = app?.state ?? (supplier.status === "verified" ? "verified" : "applied");

  async function addDocument(file: File) {
    setBusy(true);
    setError("");
    try {
      await supplierApi.uploadDocument(file);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">
          {state === "verified" ? S.verifiedTitle : state === "declined" ? S.declinedTitle : S.reviewTitle}
        </h2>
        <Badge tone={state === "verified" ? "good" : state === "declined" ? "bad" : "warn"}>
          {SUPPLIER.status[state] ?? state}
        </Badge>
      </div>
      <p className="text-text-secondary">
        {supplier.name}
        {app ? ` · ${formatDate(app.created_at)}` : ""}
      </p>
      {state === "applied" && <p className="text-text-secondary">{S.reviewText}</p>}
      {state === "declined" && app?.reason && <p className="text-text-secondary">{app.reason}</p>}
      {app && app.documents.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">{S.documents}</h3>
          <ul className="mt-1 text-sm text-text-muted">
            {app.documents.map((d) => (
              <li key={d.sha256}>
                {d.name} · {Math.ceil(d.bytes / 1024)} KB
              </li>
            ))}
          </ul>
        </div>
      )}
      {state === "applied" && me?.role === "owner" && (
        <Field label={S.addDocument}>
          <input
            type="file"
            accept="application/pdf,.pdf"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void addDocument(f);
            }}
            className="text-sm text-text-secondary"
          />
        </Field>
      )}
      {error && <ErrorNote message={error} />}
      <Link href="/supplier/" className="inline-block text-accent hover:underline">
        {S.openPortal}
      </Link>
    </div>
  );
}
