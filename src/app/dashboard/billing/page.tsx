"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Check, CreditCard, Wallet } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import {
  formatMoney,
  getCatalog,
  getSubscription,
  listPayments,
  openBillingPortal,
  refreshPayment,
  startCheckout,
  type Provider,
} from "@/lib/developer";
import { cn } from "@/lib/utils";

const nf = new Intl.NumberFormat("en-US");

const PROVIDER_COPY: Record<Provider, { label: string; detail: string; icon: typeof CreditCard }> = {
  stripe: { label: "Pay by card", detail: "Visa, Mastercard, Amex · billed monthly via Stripe", icon: CreditCard },
  wayl: { label: "Pay with Wayl", detail: "QiCard, FIB, ZainCash (Iraq) · 30 days per payment", icon: Wallet },
};

function BillingInner() {
  const user = useDashboardUser();
  const params = useSearchParams();
  const catalog = useApiData(getCatalog);
  const sub = useApiData(getSubscription);
  const payments = useApiData(listPayments);
  const [busy, setBusy] = useState<Provider | "portal" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Back from a hosted checkout: confirm the payment with the provider now,
  // in case its webhook is late (or arrived while the server was offline).
  const returned = params.get("checkout");
  const ref = params.get("ref") ?? params.get("referenceId");
  useEffect(() => {
    if (returned === "canceled") {
      setNotice("Checkout was cancelled — you haven't been charged.");
      return;
    }
    if (returned !== "success" || !ref) return;
    setNotice("Confirming your payment…");
    refreshPayment(ref)
      .then((p) => {
        setNotice(
          p.status === "paid"
            ? "Payment received — your plan is active. Thank you!"
            : "Payment is still processing. This page will show your plan once the provider confirms it."
        );
        void sub.reload();
        void payments.reload();
      })
      .catch(() => setNotice("We couldn't confirm the payment yet. It will appear here once the provider confirms it."));
    // run once per return
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [returned, ref]);

  async function checkout(provider: Provider) {
    setBusy(provider);
    setError("");
    try {
      const { url } = await startCheckout("pro", provider);
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
      setError(err instanceof Error ? err.message : "Couldn't open billing portal.");
      setBusy(null);
    }
  }

  const pro = catalog.data?.plans.find((p) => p.id === "pro");
  const free = catalog.data?.plans.find((p) => p.id === "free");
  const providers = catalog.data?.providers ?? [];
  const plan = sub.data?.plan ?? user.plan;
  const isPaid = plan !== "free";

  return (
    <>
      <PageHeader title="Billing" description="Your plan, payment methods and payment history." />

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
        <Panel>
          <h2 className="font-semibold">Current plan</h2>
          <p className="mt-4 text-3xl font-semibold capitalize">{plan === "free" ? "Starter" : plan}</p>
          {sub.data && isPaid && (
            <p className="mt-2 text-sm text-text-secondary">
              {sub.data.provider === "wayl" ? "Paid through " : "Renews "}
              {formatDate(sub.data.current_period_end)}
              {sub.data.provider && ` · via ${sub.data.provider === "wayl" ? "Wayl" : "Stripe"}`}
              {sub.data.status !== "active" && ` · ${sub.data.status.replace("_", " ")}`}
            </p>
          )}
          {!isPaid && free && (
            <p className="mt-2 text-sm text-text-secondary">
              {nf.format(free.monthly_requests)} API requests / month · {free.max_api_keys} keys
            </p>
          )}
          {sub.data?.can_manage && (
            <Button variant="secondary" size="sm" className="mt-5" onClick={manage} disabled={busy !== null}>
              {busy === "portal" ? "Opening…" : "Manage card & subscription"}
            </Button>
          )}
        </Panel>

        {pro && (
          <Panel className={cn(!isPaid && "border-accent/40")}>
            <div className="flex items-baseline justify-between">
              <h2 className="font-semibold">Professional</h2>
              <p>
                <span className="text-2xl font-semibold">
                  {formatMoney(pro.price_usd_cents ?? 0, "USD")}
                </span>
                <span className="text-text-muted"> / month</span>
              </p>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-text-secondary">
              {[
                `${nf.format(pro.monthly_requests)} API requests / month`,
                `${pro.max_api_keys} API keys`,
                "Full lighting suite and asset library",
                "Priority support",
              ].map((f) => (
                <li key={f} className="flex gap-2">
                  <Check size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                  {f}
                </li>
              ))}
            </ul>

            <div className="mt-6 space-y-3">
              {providers.length === 0 ? (
                <p className="rounded-[var(--radius-button)] border border-border bg-background px-4 py-3 text-sm text-text-secondary">
                  Online payment is being set up. To upgrade now,{" "}
                  <Link className="text-accent hover:underline" href="/#contact">
                    contact us
                  </Link>
                  .
                </p>
              ) : (
                providers.map((p) => {
                  const copy = PROVIDER_COPY[p];
                  const Icon = copy.icon;
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => checkout(p)}
                      disabled={busy !== null}
                      className="flex w-full items-center gap-4 rounded-[var(--radius-button)] border border-border bg-background px-4 py-3 text-left transition-colors hover:border-accent/50 disabled:opacity-60"
                    >
                      <Icon size={20} className="shrink-0 text-accent" aria-hidden />
                      <span className="flex-1">
                        <span className="block font-medium text-text-primary">
                          {busy === p ? "Redirecting…" : copy.label}
                          {p === "wayl" && pro.price_iqd ? ` · ${formatMoney(pro.price_iqd, "IQD")}` : ""}
                        </span>
                        <span className="block text-xs text-text-muted">{copy.detail}</span>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
            {isPaid && sub.data?.provider === "wayl" && (
              <p className="mt-3 text-xs text-text-muted">
                Paying again with Wayl adds 30 days on top of your current period.
              </p>
            )}
          </Panel>
        )}
      </div>

      <Panel className="mt-6">
        <h2 className="font-semibold">Payment history</h2>
        {!payments.data || payments.data.length === 0 ? (
          <p className="mt-4 text-sm text-text-muted">
            {payments.loading ? "Loading…" : "No payments yet."}
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Plan</th>
                  <th className="py-2 pr-4 font-medium">Method</th>
                  <th className="py-2 pr-4 text-right font-medium">Amount</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {payments.data.map((p) => (
                  <tr key={p.reference} className="border-t border-border">
                    <td className="py-2.5 pr-4 text-text-secondary">{formatDate(p.created_at)}</td>
                    <td className="py-2.5 pr-4 capitalize text-text-primary">{p.plan}</td>
                    <td className="py-2.5 pr-4 text-text-secondary">{p.provider === "wayl" ? "Wayl" : "Card"}</td>
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

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingInner />
    </Suspense>
  );
}
