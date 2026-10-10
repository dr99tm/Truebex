"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Download, Minus, Plus } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { useOrgs } from "@/components/dashboard/OrgContext";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { API_URL, formatDate } from "@/lib/api";
import { STATIC_CATALOG } from "@/lib/billing-catalog";
import { fill, foundingCovers, foundingPrice, intervalFor, perMonthOfYear } from "@/lib/catalogue";
import { BILLING, ORG_BILLING } from "@/lib/constants";
import {
  cancelSubscription,
  changePlan,
  changeSeats,
  fillWording,
  formatMoney,
  getCatalog,
  getSubscription,
  listInvoices,
  listPayments,
  openBillingPortal,
  refreshPayment,
  startCheckout,
  withdrawContract,
  type Catalog,
  type Interval,
  type PlanInfo,
  type Subscription,
} from "@/lib/developer";
import { getOrg, type OrgDetail, type Role } from "@/lib/orgs";
import { cn } from "@/lib/utils";

// PF3a: /dashboard/billing/?org=<id> is an organisation's billing page.
const ORG_ID = /^[0-9a-f]{32}$/;
const BUYER_ROLES: readonly Role[] = ["owner", "billing"];

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

type ExitStep = "cancel" | "refund" | "withdraw";

/** PF2b: end the plan inside Billing, each with a confirm step. The easy
 *  exit (cancel at the period end) is always offered for a live plan; the
 *  renewal cooling-off refund and the EU withdrawal only when the API offers
 *  them (the withdrawal's labels are GD5 7.4 wording: approved builds only). */
function ExitActions({ sub, onDone }: { sub: Subscription; onDone: (message: string) => void }) {
  const [step, setStep] = useState<ExitStep | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rules = BILLING.rules;
  const canWithdraw = !!rules && !!sub.withdrawal_until;
  if (!sub.can_cancel && !sub.cooling_off_until && !canWithdraw) return null;

  async function go(kind: ExitStep) {
    setBusy(true);
    setError("");
    try {
      const res = kind === "withdraw" ? await withdrawContract() : await cancelSubscription(kind === "refund");
      setStep(null);
      onDone(
        kind === "withdraw" && rules
          ? rules.withdrawDone
          : res.status === "processing"
            ? BILLING.exit.processing
            : BILLING.exit.sent
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the cancellation.");
    } finally {
      setBusy(false);
    }
  }

  const confirmText =
    step === "cancel"
      ? fillWording(BILLING.exit.cancelConfirm, { date: formatDate(sub.current_period_end) })
      : step === "refund"
        ? fillWording(BILLING.exit.refundConfirm, { date: formatDate(sub.cooling_off_until) })
        : step === "withdraw" && rules
          ? fillWording(rules.withdrawHint, { date: formatDate(sub.withdrawal_until) })
          : "";
  const goLabel =
    step === "cancel"
      ? BILLING.exit.cancelGo
      : step === "refund"
        ? BILLING.exit.refundGo
        : (rules?.withdrawConfirm ?? "");

  return (
    <div className="mt-5 border-t border-border pt-4">
      {step === null ? (
        <div className="flex flex-wrap gap-2">
          {sub.can_cancel && (
            <Button variant="ghost" size="sm" onClick={() => setStep("cancel")}>
              {BILLING.exit.cancel}
            </Button>
          )}
          {sub.cooling_off_until && (
            <Button variant="ghost" size="sm" onClick={() => setStep("refund")}>
              {BILLING.exit.refund}
            </Button>
          )}
          {canWithdraw && rules && (
            <Button variant="ghost" size="sm" onClick={() => setStep("withdraw")}>
              {rules.withdrawButton}
            </Button>
          )}
        </div>
      ) : (
        <div role="group" aria-label={goLabel} className="space-y-3">
          <p className="text-sm text-text-secondary">{confirmText}</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => go(step)} disabled={busy}>
              {busy ? BILLING.exit.working : goLabel}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setStep(null)} disabled={busy}>
              {BILLING.exit.keep}
            </Button>
          </div>
        </div>
      )}
      {error && (
        <div className="mt-3">
          <ErrorNote message={error} />
        </div>
      )}
    </div>
  );
}

function CurrentPlan({
  sub,
  cat,
  fallbackPlan,
  busy,
  onManage,
  children,
  isOrg = false,
}: {
  sub: Subscription | null;
  cat: Catalog;
  fallbackPlan: string;
  busy: boolean;
  onManage: () => void;
  children?: React.ReactNode;
  isOrg?: boolean;
}) {
  const tier = sub?.tier ?? fallbackPlan;
  // An organisation without a subscription has no seats (not a Free plan).
  const orgWithout = isOrg && (!sub || sub.status === "none");
  const name = orgWithout ? ORG_BILLING.noPlan : (cat.tiers.find((t) => t.id === tier)?.name ?? tier);
  // A trial is a subscription row without billing (licence contract 5.6).
  const isTrial = sub?.provider === "trial";
  const hasSub = !!sub?.provider && !isTrial;
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
      <p className="mt-4 text-3xl font-semibold">
        {name}
        {isTrial && ` ${BILLING.plan.trial}`}
      </p>
      {isTrial && sub?.current_period_end && (
        <p className="mt-2 text-sm text-text-secondary">
          {BILLING.plan.trialEnds} {formatDate(sub.current_period_end)}
        </p>
      )}
      {orgWithout && <p className="mt-2 text-sm text-text-secondary">{ORG_BILLING.noPlanHint}</p>}
      {!orgWithout && !hasSub && tier === "free" && (
        <p className="mt-2 text-sm text-text-secondary">{BILLING.plan.free}</p>
      )}
      {sub && hasSub && (
        <div className="mt-2 space-y-1 text-sm text-text-secondary">
          <p>
            {sub.interval === "year" ? BILLING.choose.annual : BILLING.choose.monthly}
            {" · "}
            {sub.seats === 1 ? BILLING.plan.oneSeat : `${sub.seats} ${BILLING.plan.seats}`}
            {isOrg && sub.seats_assigned != null && ` · ${sub.seats_assigned} ${ORG_BILLING.assigned}`}
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
      {children}
    </Panel>
  );
}

/** The billing page of the signed-in person (`org` null) or, for its owner
 *  and billing members, of an organisation (PF3a). */
function BillingManager({ org }: { org: OrgDetail | null }) {
  const user = useDashboardUser();
  const params = useSearchParams();
  const orgId = org?.id ?? null;
  const catalog = useApiData(getCatalog);
  // Keyed on the organisation by the caller, so each loader runs for one scope.
  const sub = useApiData(() => getSubscription(orgId));
  const payments = useApiData(() => listPayments(orgId));
  const invoices = useApiData(() => listInvoices(orgId));
  const cat: Catalog = catalog.data ?? STATIC_CATALOG;

  // A link like /dashboard/billing/?tier=team&interval=year&seats=5&code=X
  // preselects the plan (the pricing page's checkout links). A tier without
  // the chosen interval is sold at the one it has (Team is annual only, so
  // ?tier=team&interval=month buys the annual price).
  const [interval, setBillingInterval] = useState<Interval>(
    params.get("interval") === "year" ? "year" : "month"
  );
  const [currency, setCurrency] = useState<string>(
    () => params.get("currency")?.toUpperCase() ?? localeCurrency()
  );
  // Organisations most often buy the per-seat tier.
  const [tierId, setTierId] = useState<string>(
    params.get("tier") ?? params.get("plan") ?? (org ? "team" : "pro")
  );
  const [seatChoice, setSeatChoice] = useState<number>(
    Math.min(1000, Math.max(0, Math.floor(Number(params.get("seats")) || 0)))
  );
  const [coupon, setCoupon] = useState(params.get("code") ?? "");
  const [consent, setConsent] = useState(false);
  // PF2b (approved wording only): the key information acknowledged, and
  // GD5 7.4's optional business box.
  const [keyInfoAck, setKeyInfoAck] = useState(false);
  const [business, setBusiness] = useState(false);
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
          setNotice(org ? ORG_BILLING.paid : BILLING.notices.paid);
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
  const foundingOn = (t: PlanInfo, iv: Interval) => founding.enabled && foundingCovers(founding, t.id, iv);
  const unitPrice = (t: PlanInfo, iv: Interval) => {
    const p = priceOf(t, iv, activeCurrency);
    if (!p) return null;
    return foundingOn(t, iv) ? foundingPrice(p.amount_minor, founding.discount_percent) : p.amount_minor;
  };
  // The interval the selected tier is bought at.
  const selectedInterval = tier ? intervalFor(tier, interval, activeCurrency) : interval;
  const selectedUnit = tier ? unitPrice(tier, selectedInterval) : null;

  // PF2b: which cancellation wording checkout carries. The API says whether
  // GD5 7.4 is approved and which QS-17 variant applies; this build has the
  // approved texts only when compiled with them (BILLING.rules).
  const rules = BILLING.rules;
  const serverRules = catalog.data?.rules;
  const approved = !!serverRules?.wording_approved;
  const consentShown = approved
    ? rules &&
      (serverRules?.consent_variant === "service"
        ? { text: rules.consentService, version: rules.consentServiceVersion }
        : { text: rules.consentDigital, version: rules.consentDigitalVersion })
    : { text: BILLING.consent.label, version: BILLING.consent.version };
  const termsMismatch =
    !!serverRules &&
    (!consentShown ||
      consentShown.version !== serverRules.consent_version ||
      (approved && serverRules.key_info_version !== rules?.draftVersion));
  const keyInfo =
    approved && rules && tier && selectedUnit !== null
      ? fillWording(rules.keyInfo, {
          plan: tier.per_seat ? `${tier.name}, ${seats} seats` : tier.name,
          price: formatMoney(selectedUnit * seats, activeCurrency),
          interval: per(selectedInterval),
          currency: activeCurrency,
          seller: cat.provider === "stripe" ? rules.sellerStripe : rules.sellerPaddle,
        })
      : null;
  const ready = consent && (!approved || keyInfoAck);

  const current = sub.data;
  const managed = !!current?.provider && MANAGED.has(current.provider);
  const managedActive = managed && current?.status === "active";
  // A past-due or paused subscription is fixed under Manage, not bought again;
  // an organisation buys only while it has no subscription (seats set up by
  // hand included).
  const showChoose = org
    ? !managed && (current?.status ?? "none") === "none"
    : !managed && (current?.tier ?? user.plan) !== "enterprise";

  async function checkout() {
    if (!tier || !ready || !consentShown) return;
    setBusy("checkout");
    setError("");
    try {
      const { url } = await startCheckout({
        tier: tier.id,
        interval: selectedInterval,
        currency: activeCurrency,
        seats,
        coupon: coupon.trim() || undefined,
        consent: { version: consentShown.version, accepted: true },
        ...(approved && rules
          ? { key_info: { version: rules.draftVersion, acknowledged: true as const }, business }
          : {}),
        org_id: orgId ?? undefined,
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
      window.location.href = (await openBillingPortal(orgId)).url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open the billing portal.");
      setBusy(null);
    }
  }

  // After a cancellation: the plan card follows once the provider's webhook
  // lands, so look again a few times.
  function exited(message: string) {
    setNotice(message);
    void sub.reload();
    for (const ms of [3000, 8000]) window.setTimeout(() => void sub.reload(), ms);
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
      <PageHeader
        title={BILLING.title}
        description={org ? `${ORG_BILLING.description} ${org.name}.` : BILLING.description}
      />
      {org && <ConsoleLink />}

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
          fallbackPlan={org ? "free" : user.plan}
          busy={busy === "portal"}
          onManage={manage}
          isOrg={!!org}
        >
          {/* PF2b's exits are for the person's own plan (an organisation's is a business purchase). */}
          {managed && current && !org && <ExitActions sub={current} onDone={exited} />}
        </CurrentPlan>
        {managedActive && current && (
          // Keyed on the subscription so the form resets after a change.
          <ChangePanel
            key={`${current.tier}-${current.interval}-${current.seats}`}
            sub={current}
            cat={cat}
            busy={busy}
            run={run}
            orgId={orgId}
          />
        )}
      </div>

      {!org && <OrgsYouBuyFor />}

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
              const iv = intervalFor(t, interval, activeCurrency);
              const list = priceOf(t, iv, activeCurrency);
              const unit = unitPrice(t, iv);
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
                  ) : iv !== interval && iv === "year" ? (
                    // Annual only (Team) in the Monthly view: what the annual
                    // charge comes to per month, then the charge itself.
                    <span className="mt-3 block">
                      <span className="text-2xl font-semibold text-text-primary">
                        {formatMoney(perMonthOfYear(unit), activeCurrency)}
                      </span>
                      <span className="text-sm text-text-muted"> / month, {BILLING.choose.billedAnnually}</span>
                      <span className="mt-0.5 block text-xs text-text-muted">
                        {formatMoney(unit, activeCurrency)} / year
                        {unit !== list.amount_minor && (
                          <span className="ml-2 line-through">{formatMoney(list.amount_minor, activeCurrency)}</span>
                        )}
                      </span>
                    </span>
                  ) : (
                    <span className="mt-3 block">
                      <span className="text-2xl font-semibold text-text-primary">{formatMoney(unit, activeCurrency)}</span>
                      <span className="text-sm text-text-muted"> / {per(iv)}</span>
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
                <Link href="/pricing/" className="text-accent hover:underline">
                  {BILLING.choose.compare}
                </Link>
              </p>
            </div>

            <div className="space-y-4">
              {keyInfo && rules ? (
                // GD5 7.4 "Before payment": the key information beside the button.
                <div className="rounded-[var(--radius-button)] border border-accent/30 bg-accent/5 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-text-muted">{rules.keyInfoHeading}</p>
                  <p className="mt-1 text-sm text-text-primary">{keyInfo}</p>
                  {tier && selectedInterval !== interval && (
                    <span className="mt-1 block text-xs text-text-muted">
                      {fill(BILLING.choose.annualOnly, { tier: tier.name })}
                    </span>
                  )}
                </div>
              ) : (
                selectedUnit !== null && (
                  <p className="text-sm text-text-secondary">
                    {BILLING.choose.total}:{" "}
                    <span className="font-semibold tabular-nums text-text-primary">
                      {formatMoney(selectedUnit * seats, activeCurrency)}
                    </span>{" "}
                    / {per(selectedInterval)}
                    {tier && selectedInterval !== interval && (
                      <span className="mt-1 block text-xs text-text-muted">
                        {fill(BILLING.choose.annualOnly, { tier: tier.name })}
                      </span>
                    )}
                    <span className="mt-1 block text-xs text-text-muted">{BILLING.choose.tax}</span>
                  </p>
                )
              )}
              {keyInfo && rules && (
                <label className="flex items-start gap-3 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={keyInfoAck}
                    onChange={(e) => setKeyInfoAck(e.target.checked)}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                  />
                  <span>{rules.keyInfoAck}</span>
                </label>
              )}
              {consentShown && (
                <label className="flex items-start gap-3 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                  />
                  <span>{consentShown.text}</span>
                </label>
              )}
              {approved && rules && (
                <label className="flex items-start gap-3 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={business}
                    onChange={(e) => setBusiness(e.target.checked)}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
                  />
                  <span>{rules.business}</span>
                </label>
              )}
              {catalog.data && (cat.provider === null || termsMismatch) ? (
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
                    disabled={!ready || busy !== null || selectedUnit === null || !cat.provider}
                    className="disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy === "checkout" ? BILLING.choose.redirecting : BILLING.choose.checkout}
                  </Button>
                  {!ready && (
                    <p className="mt-2 text-xs text-text-muted">
                      {approved && rules ? rules.reasons : BILLING.consent.reason}
                    </p>
                  )}
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
  orgId,
}: {
  sub: Subscription;
  cat: Catalog;
  busy: string | null;
  run: (label: string, action: () => Promise<Subscription>) => Promise<void>;
  orgId: string | null;
}) {
  const buyable = cat.tiers.filter((t) => t.purchasable);
  const [tierId, setTierId] = useState(sub.tier);
  const [interval, setBillingInterval] = useState<Interval>(sub.interval ?? "month");
  const [seats, setSeats] = useState(sub.seats);
  const currency = sub.currency ?? "GBP";
  const target = buyable.find((t) => t.id === tierId);
  const currentTier = cat.tiers.find((t) => t.id === sub.tier);
  // Team is annual only: a move to it is a move to annual billing.
  const iv = target ? intervalFor(target, interval, currency) : interval;
  const changed = tierId !== sub.tier || iv !== (sub.interval ?? "month");
  const list = target ? priceOf(target, iv, currency) : null;
  // The founding price follows the subscription only where the offer covers
  // the new tier and interval (server: BillingProvider.change_subscription).
  const keepsFounding = !!sub.founding && foundingCovers(cat.founding, tierId, iv);

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
          {formatMoney(
            keepsFounding ? foundingPrice(list.amount_minor, cat.founding.discount_percent) : list.amount_minor,
            currency
          )}{" "}
          / {per(iv)}
          {target?.per_seat && ` ${BILLING.choose.perSeat}`}
          {target && iv !== interval && (
            <span className="mt-1 block text-xs text-text-muted">
              {fill(BILLING.choose.annualOnly, { tier: target.name })}
            </span>
          )}
        </p>
      )}
      {changed && sub.founding && !keepsFounding && (
        <p className="mt-2 text-xs text-warn">{BILLING.change.foundingEnds}</p>
      )}
      <Button
        size="sm"
        className="mt-4 disabled:cursor-not-allowed disabled:opacity-50"
        disabled={!changed || busy !== null}
        onClick={() => run("change", () => changePlan({ tier: tierId, interval: iv }, orgId))}
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
              onClick={() => run("seats", () => changeSeats(seats, orgId))}
            >
              {busy === "seats" ? BILLING.change.applying : BILLING.change.seatsApply}
            </Button>
          </div>
          {orgId && sub.seats_assigned != null && (
            <p className="mt-3 text-xs text-text-muted">
              {sub.seats_assigned} {ORG_BILLING.assigned}. {ORG_BILLING.assignedHint}{" "}
              <Link href="/dashboard/organisation/seats/" className="text-accent hover:underline">
                {ORG_BILLING.seatsTab}
              </Link>
            </p>
          )}
        </div>
      )}
      <p className="mt-4 text-xs text-text-muted">{BILLING.change.prorated}</p>
    </Panel>
  );
}

function ConsoleLink() {
  return (
    <p className="-mt-4 mb-6 text-sm">
      <Link href="/dashboard/organisation/" className="inline-flex items-center gap-1 text-accent hover:underline">
        <ArrowLeft size={14} aria-hidden />
        {ORG_BILLING.console}
      </Link>
    </p>
  );
}

/** On the person's own billing page: the organisations they buy for. */
function OrgsYouBuyFor() {
  const { orgs } = useOrgs();
  const mine = orgs.filter((o) => BUYER_ROLES.includes(o.role));
  if (mine.length === 0) return null;
  return (
    <Panel className="mt-6">
      <h2 className="font-semibold">{ORG_BILLING.yourOrgs}</h2>
      <p className="mt-1 text-sm text-text-muted">{ORG_BILLING.yourOrgsHint}</p>
      <ul className="mt-4 space-y-2 text-sm">
        {mine.map((o) => (
          <li key={o.id} className="flex items-center justify-between gap-3">
            <span className="text-text-primary">{o.name}</span>
            <a href={`/dashboard/billing/?org=${o.id}`} className="inline-flex items-center gap-1 text-accent hover:underline">
              {ORG_BILLING.openBilling} <ArrowRight size={14} aria-hidden />
            </a>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/** Admins and members see the organisation's plan, read-only. */
function OrgReadOnly({ org }: { org: OrgDetail }) {
  const s = org.subscription;
  return (
    <>
      <PageHeader title={BILLING.title} description={`${ORG_BILLING.description} ${org.name}.`} />
      <ConsoleLink />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <h2 className="font-semibold">{BILLING.plan.heading}</h2>
          <p className="mt-4 text-3xl font-semibold">{s ? s.plan_name : ORG_BILLING.noPlan}</p>
          {s && (
            <div className="mt-2 space-y-1 text-sm text-text-secondary">
              <p>{s.seats === 1 ? BILLING.plan.oneSeat : `${s.seats} ${BILLING.plan.seats}`}</p>
              {s.current_period_end && (
                <p>
                  {ORG_BILLING.paidUntil} {formatDate(s.current_period_end)}
                </p>
              )}
            </div>
          )}
          <p className="mt-5 text-sm text-text-muted">{ORG_BILLING.readOnly}</p>
        </Panel>
      </div>
    </>
  );
}

/** Loads the organisation (any member may), then the page its role gets. */
function OrgBilling({ orgId }: { orgId: string }) {
  const detail = useApiData(() => getOrg(orgId));
  const org = detail.data;
  if (!org) {
    return (
      <>
        <PageHeader title={BILLING.title} description={detail.error ? undefined : ORG_BILLING.loading} />
        {detail.error && <ErrorNote message={detail.error} />}
      </>
    );
  }
  return BUYER_ROLES.includes(org.role) ? <BillingManager org={org} /> : <OrgReadOnly org={org} />;
}

function BillingSwitch() {
  const params = useSearchParams();
  const org = params.get("org");
  if (org === null) return <BillingManager org={null} />;
  if (!ORG_ID.test(org)) {
    return (
      <>
        <PageHeader title={BILLING.title} />
        <ErrorNote message={ORG_BILLING.invalid} />
      </>
    );
  }
  return <OrgBilling key={org} orgId={org} />;
}

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingSwitch />
    </Suspense>
  );
}
