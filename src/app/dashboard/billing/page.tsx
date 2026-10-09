"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Check, Download, Minus, Plus } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { API_URL, formatDate } from "@/lib/api";
import { STATIC_CATALOG, foundingPrice } from "@/lib/catalogue";
import { BILLING } from "@/lib/constants";
import {
  changePlan,
  changeSeats,
  formatMoney,
  getCatalog,
  getSubscription,
  listInvoices,
  listPayments,
  openBillingPortal,
  refreshPayment,
  startCheckout,
  type Catalog,
  type Interval,
  type PlanInfo,
  type Subscription,
} from "@/lib/developer";
import { cn } from "@/lib/utils";

// Eurozone regions: the browser's locale picks EUR there, USD in the US and
// GBP everywhere else (the company bills from the UK).
const EUR_REGIONS = new Set([
  "AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR",
  "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK",
]);

function localeCurrency(): string {
  if (typeof navigator === "undefined") return "GBP";
  try {
    const region = new Intl.Locale(navigator.language).maximize().region ?? "";
    if (region === "US") return "USD";
    if (EUR_REGIONS.has(region)) return "EUR";
  } catch {
    /* unknown locale */
  }
  return "GBP";
}

const MANAGED = new Set(["paddle", "stripe"]);

function providerLabel(provider: string): string {
  if (MANAGED.has(provider)) return BILLING.history.card;
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

function priceOf(tier: PlanInfo, interval: Interval, currency: string) {
  return tier.prices.find((p) => p.interval === interval && p.currency === currency) ?? null;
}

/** Whole-percent saving of paying a year at once, for this tier and currency. */
function annualSaving(tier: PlanInfo | undefined, currency: string): number {
  if (!tier) return 0;
  const m = priceOf(tier, "month", currency);
  const y = priceOf(tier, "year", currency);
  if (!m || !y || m.amount_minor <= 0) return 0;
  return Math.max(0, Math.round((1 - y.amount_minor / (12 * m.amount_minor)) * 100));
}

function per(interval: Interval | null): string {
  return interval === "year" ? "year" : "month";
}

function SeatStepper({
  value,
  min,
  onChange,
  disabled,
}: {
  value: number;
  min: number;
  onChange: (n: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        aria-label="One seat fewer"
        disabled={disabled || value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
        className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-button)] border border-border text-text-secondary hover:border-accent/50 disabled:opacity-40"
      >
        <Minus size={14} aria-hidden />
      </button>
      <input
        type="number"
        inputMode="numeric"
        min={min}
        max={1000}
        value={value}
        disabled={disabled}
        aria-label={BILLING.choose.seats}
        onChange={(e) => onChange(Math.min(1000, Math.max(min, Number(e.target.value) || min)))}
        className="h-9 w-16 rounded-[var(--radius-button)] border border-border bg-background text-center tabular-nums text-text-primary"
      />
      <button
        type="button"
        aria-label="One seat more"
        disabled={disabled || value >= 1000}
        onClick={() => onChange(value + 1)}
        className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-button)] border border-border text-text-secondary hover:border-accent/50 disabled:opacity-40"
      >
        <Plus size={14} aria-hidden />
      </button>
    </div>
  );
}

function IntervalToggle({
  value,
  onChange,
  saving,
  disabled,
}: {
  value: Interval;
  onChange: (v: Interval) => void;
  saving: number;
  disabled?: boolean;
}) {
  const options: { id: Interval; label: string }[] = [
    { id: "month", label: BILLING.choose.monthly },
    { id: "year", label: BILLING.choose.annual },
  ];
  return (
    <div role="group" aria-label={BILLING.change.interval} className="inline-flex rounded-[var(--radius-button)] border border-border p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={value === o.id}
          disabled={disabled}
          onClick={() => onChange(o.id)}
          className={cn(
            "rounded-[calc(var(--radius-button)-2px)] px-3 py-1.5 text-sm transition-colors",
            value === o.id ? "bg-accent/15 text-accent" : "text-text-secondary hover:text-text-primary"
          )}
        >
          {o.label}
          {o.id === "year" && saving > 0 && (
            <span className="ml-1.5 text-xs text-warn">
              {BILLING.choose.save} {saving}%
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function CurrentPlan({
  sub,
  cat,
  fallbackPlan,
  busy,
  onManage,
}: {
  sub: Subscription | null;
  cat: Catalog;
  fallbackPlan: string;
  busy: boolean;
  onManage: () => void;
}) {
  const tier = sub?.tier ?? fallbackPlan;
  const name = cat.tiers.find((t) => t.id === tier)?.name ?? tier;
  const hasSub = !!sub?.provider;
  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold">{BILLING.plan.heading}</h2>
        {sub?.founding && (
          <span className="rounded-full border border-warn/40 px-2.5 py-0.5 text-xs text-warn">
            {BILLING.plan.founding}
          </span>
        )}
      </div>
      <p className="mt-4 text-3xl font-semibold">{name}</p>
      {!hasSub && tier === "free" && (
        <p className="mt-2 text-sm text-text-secondary">{BILLING.plan.free}</p>
      )}
      {sub && hasSub && (
        <div className="mt-2 space-y-1 text-sm text-text-secondary">
          <p>
            {sub.interval === "year" ? BILLING.choose.annual : BILLING.choose.monthly}
            {" · "}
            {sub.seats === 1 ? BILLING.plan.oneSeat : `${sub.seats} ${BILLING.plan.seats}`}
            {sub.provider && !MANAGED.has(sub.provider) && ` · ${providerLabel(sub.provider)}`}
          </p>
          {sub.current_period_end && (
            <p>
              {sub.cancel_at_period_end ? BILLING.plan.ends : BILLING.plan.renews}{" "}
              {formatDate(sub.current_period_end)}
            </p>
          )}
          {sub.status === "past_due" && <p className="text-warn">{BILLING.plan.pastDue}</p>}
          {sub.status === "paused" && <p className="text-warn">{BILLING.plan.paused}</p>}
        </div>
      )}
      {sub?.can_manage && (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onManage} disabled={busy}>
          {busy ? BILLING.plan.opening : BILLING.plan.manage}
        </Button>
      )}
    </Panel>
  );
}

function BillingInner() {
  const user = useDashboardUser();
  const params = useSearchParams();
  const catalog = useApiData(getCatalog);
  const sub = useApiData(getSubscription);
  const payments = useApiData(listPayments);
  const invoices = useApiData(listInvoices);
  const cat: Catalog = catalog.data ?? STATIC_CATALOG;

  // A link like /dashboard/billing/?tier=team&interval=year&seats=5&code=X
  // preselects the plan (the pricing page's checkout links).
  const [interval, setBillingInterval] = useState<Interval>(
    params.get("interval") === "year" ? "year" : "month"
  );
  const [currency, setCurrency] = useState<string>(
    () => params.get("currency")?.toUpperCase() ?? localeCurrency()
  );
  const [tierId, setTierId] = useState<string>(params.get("tier") ?? params.get("plan") ?? "pro");
  const [seatChoice, setSeatChoice] = useState<number>(Number(params.get("seats")) || 0);
  const [coupon, setCoupon] = useState(params.get("code") ?? "");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Back from checkout: confirm the payment with the provider now, in case
  // its webhook is late (or arrived while the server was offline).
  const returned = params.get("checkout");
  const ref = params.get("ref") ?? params.get("referenceId");
  useEffect(() => {
    if (returned === "canceled") {
      setNotice(BILLING.notices.canceled);
      return;
    }
    if (returned !== "success" || !ref) return;
    let cancelled = false;
    setNotice(BILLING.notices.confirming);
    const attempt = async (n: number): Promise<void> => {
      try {
        const p = await refreshPayment(ref);
        if (cancelled) return;
        if (p.status === "paid") {
          setNotice(BILLING.notices.paid);
        } else if (n < 2) {
          await new Promise((r) => setTimeout(r, 3000 * (n + 1)));
          return attempt(n + 1);
        } else {
          setNotice(BILLING.notices.processing);
        }
      } catch {
        if (!cancelled) setNotice(BILLING.notices.unconfirmed);
      }
      void sub.reload();
      void payments.reload();
      void invoices.reload();
    };
    void attempt(0);
    return () => {
      cancelled = true;
    };
    // run once per return
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [returned, ref]);

  const currencies = cat.currencies.length ? cat.currencies : ["GBP", "USD", "EUR"];
  const activeCurrency = currencies.includes(currency) ? currency : currencies[0];
  const buyable = cat.tiers.filter((t) => t.purchasable);
  const tier = buyable.find((t) => t.id === tierId) ?? buyable[0];
  const seats = tier?.per_seat ? Math.max(seatChoice || tier.min_seats, tier.min_seats) : 1;
  const founding = cat.founding;
  const foundingOn = (t: PlanInfo | undefined) => !!t && founding.enabled && founding.tiers.includes(t.id);
  const unitPrice = (t: PlanInfo, iv: Interval) => {
    const p = priceOf(t, iv, activeCurrency);
    if (!p) return null;
    return foundingOn(t) ? foundingPrice(p.amount_minor, founding.discount_percent) : p.amount_minor;
  };
  const selectedUnit = tier ? unitPrice(tier, interval) : null;

  const current = sub.data;
  const managed = !!current?.provider && MANAGED.has(current.provider);
  const managedActive = managed && current?.status === "active";
  // A past-due or paused subscription is fixed under Manage, not bought again.
  const showChoose = !managed && (current?.tier ?? user.plan) !== "enterprise";

  async function checkout() {
    if (!tier || !consent) return;
    setBusy("checkout");
    setError("");
    try {
      const { url } = await startCheckout({
        tier: tier.id,
        interval,
        currency: activeCurrency,
        seats,
        coupon: coupon.trim() || undefined,
        consent: { version: BILLING.consent.version, accepted: true },
      });
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout.");
      setBusy(null);
    }
  }

  async function manage() {
    setBusy("portal");
    setError("");
    try {
      window.location.href = (await openBillingPortal()).url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open the billing portal.");
      setBusy(null);
    }
  }

  async function run(label: string, action: () => Promise<Subscription>) {
    if (!window.confirm(BILLING.change.confirm)) return;
    setBusy(label);
    setError("");
    try {
      sub.setData(await action());
      setNotice(BILLING.change.done);
      void invoices.reload();
      void payments.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't change the subscription.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title={BILLING.title} description={BILLING.description} />

      {notice && (
        <p role="status" className="mb-6 rounded-[var(--radius-button)] border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-text-primary">
          {notice}
        </p>
      )}
      {(error || catalog.error || sub.error) && (
        <div className="mb-6">
          <ErrorNote message={error || catalog.error || sub.error || ""} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <CurrentPlan
          sub={current}
          cat={cat}
          fallbackPlan={user.plan}
          busy={busy === "portal"}
          onManage={manage}
        />
        {managedActive && current && (
          // Keyed on the subscription so the form resets after a change.
          <ChangePanel
            key={`${current.tier}-${current.interval}-${current.seats}`}
            sub={current}
            cat={cat}
            busy={busy}
            run={run}
          />
        )}
      </div>

      {showChoose && (
        <Panel className="mt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="font-semibold">{BILLING.choose.heading}</h2>
            <div className="flex flex-wrap items-center gap-3">
              <IntervalToggle value={interval} onChange={setBillingInterval} saving={annualSaving(tier, activeCurrency)} />
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                {BILLING.choose.currency}
                <select
                  value={activeCurrency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="h-9 rounded-[var(--radius-button)] border border-border bg-background px-2 text-text-primary"
                >
                  {currencies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {founding.enabled && (
            <p className="mt-4 rounded-[var(--radius-button)] border border-warn/30 bg-warn/5 px-4 py-2.5 text-sm text-text-primary">
              <strong className="text-warn">
                {founding.remaining} {BILLING.founding.left}
              </strong>
              {" · "}
              {founding.discount_percent}% {BILLING.founding.off}
            </p>
          )}

          <div role="radiogroup" aria-label={BILLING.choose.heading} className="mt-5 grid gap-4 md:grid-cols-3">
            {buyable.map((t) => {
              const list = priceOf(t, interval, activeCurrency);
              const unit = unitPrice(t, interval);
              const selected = tier?.id === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => setTierId(t.id)}
                  className={cn(
                    "rounded-[var(--radius-card)] border bg-background p-4 text-left transition-colors",
                    selected ? "border-accent" : "border-border hover:border-accent/40"
                  )}
                >
                  <span className="flex items-center justify-between">
                    <span className="font-semibold text-text-primary">{t.name}</span>
                    {selected && <Check size={16} className="text-accent" aria-hidden />}
                  </span>
                  {unit === null || !list ? (
                    <span className="mt-3 block text-sm text-text-muted">{BILLING.choose.noPrice}</span>
                  ) : (
                    <span className="mt-3 block">
                      <span className="text-2xl font-semibold text-text-primary">{formatMoney(unit, activeCurrency)}</span>
                      <span className="text-sm text-text-muted"> / {per(interval)}</span>
                      {unit !== list.amount_minor && (
                        <span className="ml-2 text-sm text-text-muted line-through">
                          {formatMoney(list.amount_minor, activeCurrency)}
                        </span>
                      )}
                    </span>
                  )}
                  <span className="mt-1 block text-xs text-text-muted">
                    {t.per_seat
                      ? `${BILLING.choose.perSeat} · ${BILLING.choose.minSeats} ${t.min_seats}`
                      : BILLING.choose.oneSeat}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div className="space-y-4">
              {tier?.per_seat && (
                <div>
                  <p className="mb-2 text-sm text-text-secondary">{BILLING.choose.seats}</p>
                  <SeatStepper value={seats} min={tier.min_seats} onChange={setSeatChoice} />
                </div>
              )}
              <label className="block text-sm text-text-secondary">
                {BILLING.choose.coupon}
                <input
                  type="text"
                  value={coupon}
                  onChange={(e) => setCoupon(e.target.value)}
                  placeholder={BILLING.choose.couponHint}
                  maxLength={64}
                  autoComplete="off"
                  className="mt-2 block h-10 w-full max-w-xs rounded-[var(--radius-button)] border border-border bg-background px-3 text-text-primary placeholder:text-text-muted"
                />
              </label>
              <p className="text-sm">
                <Link href="/#pricing" className="text-accent hover:underline">
                  {BILLING.choose.compare}
                </Link>
              </p>
            </div>

            <div className="space-y-4">
              {selectedUnit !== null && (
                <p className="text-sm text-text-secondary">
                  {BILLING.choose.total}:{" "}
                  <span className="font-semibold tabular-nums text-text-primary">
                    {formatMoney(selectedUnit * seats, activeCurrency)}
                  </span>{" "}
                  / {per(interval)}
                  <span className="mt-1 block text-xs text-text-muted">{BILLING.choose.tax}</span>
                </p>
              )}
              <label className="flex items-start gap-3 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                />
                <span>{BILLING.consent.label}</span>
              </label>
              {catalog.data && cat.provider === null ? (
                <p className="rounded-[var(--radius-button)] border border-border bg-background px-4 py-3 text-sm text-text-secondary">
                  {BILLING.choose.setupPending}{" "}
                  <Link className="text-accent hover:underline" href="/#contact">
                    {BILLING.choose.contact}
                  </Link>
                  .
                </p>
              ) : (
                <div>
                  <Button
                    onClick={checkout}
                    disabled={!consent || busy !== null || selectedUnit === null || !cat.provider}
                    className="disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy === "checkout" ? BILLING.choose.redirecting : BILLING.choose.checkout}
                  </Button>
                  {!consent && <p className="mt-2 text-xs text-text-muted">{BILLING.consent.reason}</p>}
                  {cat.provider && (
                    <p className="mt-3 text-xs text-text-muted">{BILLING.providerNote[cat.provider]}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </Panel>
      )}

      <Panel className="mt-6">
        <h2 className="font-semibold">{BILLING.invoices.heading}</h2>
        {!invoices.data || invoices.data.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">
            {invoices.loading ? "Loading…" : invoices.error ? invoices.error : BILLING.invoices.none}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">{BILLING.invoices.date}</th>
                  <th className="py-2 pr-4 font-medium">{BILLING.invoices.number}</th>
                  <th className="py-2 pr-4 text-right font-medium">{BILLING.invoices.total}</th>
                  <th className="py-2 pr-4 text-right font-medium">{BILLING.invoices.tax}</th>
                  <th className="py-2 font-medium">{BILLING.invoices.pdf}</th>
                </tr>
              </thead>
              <tbody>
                {invoices.data.map((inv) => (
                  <tr key={inv.id} className="border-t border-border">
                    <td className="py-2.5 pr-4 text-text-secondary">{formatDate(inv.issued_at)}</td>
                    <td className="py-2.5 pr-4 text-text-primary">{inv.number ?? "—"}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-primary">
                      {formatMoney(inv.total_minor, inv.currency)}
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                      {formatMoney(inv.tax_minor, inv.currency)}
                    </td>
                    <td className="py-2.5">
                      {inv.pdf_url ? (
                        <a
                          href={inv.pdf_url.startsWith("/") ? `${API_URL}${inv.pdf_url}` : inv.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-accent hover:underline"
                        >
                          <Download size={14} aria-hidden />
                          {BILLING.invoices.download}
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel className="mt-6">
        <h2 className="font-semibold">{BILLING.history.heading}</h2>
        {!payments.data || payments.data.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">
            {payments.loading ? "Loading…" : BILLING.history.none}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">{BILLING.history.date}</th>
                  <th className="py-2 pr-4 font-medium">{BILLING.history.plan}</th>
                  <th className="py-2 pr-4 font-medium">{BILLING.history.method}</th>
                  <th className="py-2 pr-4 text-right font-medium">{BILLING.history.amount}</th>
                  <th className="py-2 font-medium">{BILLING.history.status}</th>
                </tr>
              </thead>
              <tbody>
                {payments.data.map((p) => (
                  <tr key={p.reference} className="border-t border-border">
                    <td className="py-2.5 pr-4 text-text-secondary">{formatDate(p.created_at)}</td>
                    <td className="py-2.5 pr-4 text-text-primary">
                      {cat.tiers.find((t) => t.id === p.plan)?.name ?? p.plan}
                      {p.interval && (
                        <span className="text-text-muted">
                          {" · "}
                          {p.interval === "year" ? BILLING.choose.annual : BILLING.choose.monthly}
                        </span>
                      )}
                      {p.seats && p.seats > 1 && <span className="text-text-muted"> · {p.seats}</span>}
                    </td>
                    <td className="py-2.5 pr-4 text-text-secondary">{providerLabel(p.provider)}</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-text-primary">
                      {formatMoney(p.amount, p.currency)}
                    </td>
                    <td className="py-2.5 capitalize">
                      <span
                        className={cn(
                          p.status === "paid" && "text-emerald-400",
                          p.status === "pending" && "text-warn",
                          (p.status === "failed" || p.status === "canceled") && "text-red-400"
                        )}
                      >
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

function ChangePanel({
  sub,
  cat,
  busy,
  run,
}: {
  sub: Subscription;
  cat: Catalog;
  busy: string | null;
  run: (label: string, action: () => Promise<Subscription>) => Promise<void>;
}) {
  const buyable = cat.tiers.filter((t) => t.purchasable);
  const [tierId, setTierId] = useState(sub.tier);
  const [interval, setBillingInterval] = useState<Interval>(sub.interval ?? "month");
  const [seats, setSeats] = useState(sub.seats);
  const currency = sub.currency ?? "GBP";
  const target = buyable.find((t) => t.id === tierId);
  const currentTier = cat.tiers.find((t) => t.id === sub.tier);
  const changed = tierId !== sub.tier || interval !== (sub.interval ?? "month");
  const list = target ? priceOf(target, interval, currency) : null;

  return (
    <Panel>
      <h2 className="font-semibold">{BILLING.change.heading}</h2>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          {BILLING.change.plan}
          <select
            value={tierId}
            onChange={(e) => setTierId(e.target.value)}
            className="h-9 rounded-[var(--radius-button)] border border-border bg-background px-2 text-text-primary"
          >
            {buyable.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <IntervalToggle value={interval} onChange={setBillingInterval} saving={annualSaving(target, currency)} />
      </div>
      {list && (
        <p className="mt-3 text-sm text-text-secondary">
          {formatMoney(sub.founding ? foundingPrice(list.amount_minor, cat.founding.discount_percent) : list.amount_minor, currency)}{" "}
          / {per(interval)}
          {target?.per_seat && ` ${BILLING.choose.perSeat}`}
        </p>
      )}
      <Button
        size="sm"
        className="mt-4 disabled:cursor-not-allowed disabled:opacity-50"
        disabled={!changed || busy !== null}
        onClick={() => run("change", () => changePlan({ tier: tierId, interval }))}
      >
        {busy === "change" ? BILLING.change.applying : BILLING.change.apply}
      </Button>

      {currentTier?.per_seat && (
        <div className="mt-6 border-t border-border pt-5">
          <p className="mb-2 text-sm text-text-secondary">{BILLING.change.seatsHeading}</p>
          <div className="flex flex-wrap items-center gap-3">
            <SeatStepper value={seats} min={currentTier.min_seats} onChange={setSeats} disabled={busy !== null} />
            <Button
              size="sm"
              variant="secondary"
              disabled={seats === sub.seats || busy !== null}
              className="disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => run("seats", () => changeSeats(seats))}
            >
              {busy === "seats" ? BILLING.change.applying : BILLING.change.seatsApply}
            </Button>
          </div>
        </div>
      )}
      <p className="mt-4 text-xs text-text-muted">{BILLING.change.prorated}</p>
    </Panel>
  );
}

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingInner />
    </Suspense>
  );
}
