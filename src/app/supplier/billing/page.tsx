"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { Badge, OkNote, useMember } from "@/components/supplier/SupplierShell";
import { SUPPLIER, SUPPLIER_CHECKOUT } from "@/lib/constants";
import { refreshPayment } from "@/lib/developer";
import { fill, formatMoney, supplierApi, type ListingView, type Statements } from "@/lib/supplier";

const B = SUPPLIER.billing;
const R = SUPPLIER_CHECKOUT;
// A listing plan's payments carry its billing tier, `listing_<plan>` (PF8).
const LISTING_TIER = "listing_";

// The listing plan (paid through Truebex's billing), the monthly commission
// statements with their invoices, and the Stripe payout connection.
function BillingInner() {
  useMember();
  const params = useSearchParams();
  const [view, setView] = useState<ListingView | null>(null);
  const [statements, setStatements] = useState<Statements | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState(params.get("connect") === "done" ? B.connecting : "");
  const [busy, setBusy] = useState(false);
  const [back, setBack] = useState<{ ok: boolean; text: string } | null>(null);
  const returned = params.get("checkout");
  const ref = params.get("ref");

  useEffect(() => {
    let cancelled = false;
    Promise.all([supplierApi.listing(), supplierApi.statements()])
      .then(([v, s]) => {
        if (cancelled) return;
        setView(v);
        setStatements(s);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Back from a listing plan's checkout (PF2d): confirm the payment with the
  // provider now, in case its webhook is late, then show the plan's state.
  useEffect(() => {
    if (returned === "canceled") {
      setBack({ ok: false, text: R.canceled });
      return;
    }
    if (returned !== "success" || !ref) return;
    let cancelled = false;
    setBack({ ok: true, text: R.confirming });
    const attempt = async (n: number): Promise<void> => {
      try {
        const p = await refreshPayment(ref);
        if (cancelled) return;
        if (p.status === "pending" && n < 2) {
          await new Promise((r) => setTimeout(r, 3000 * (n + 1)));
          return attempt(n + 1);
        }
        const v = await supplierApi.listing();
        if (cancelled) return;
        setView(v);
        const plan = v.plans.find((x) => LISTING_TIER + x.id === p.plan);
        if (p.status === "paid" && plan && v.plan === plan.id) setBack({ ok: true, text: fill(R.active, { plan: plan.name }) });
        else if (p.status === "paid") setBack({ ok: true, text: R.paid });
        else if (p.status === "canceled") setBack({ ok: false, text: R.canceled });
        else setBack({ ok: false, text: R.processing });
      } catch {
        if (!cancelled) setBack({ ok: false, text: R.unconfirmed });
      }
    };
    void attempt(0);
    return () => {
      cancelled = true;
    };
  }, [returned, ref]);

  async function choose(plan: string) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const res = await supplierApi.chooseListing(plan);
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
        return;
      }
      setView(res.listing);
      if (res.state === "pending") setNote(res.detail ?? B.pending);
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  async function open(fn: () => Promise<{ url: string }>) {
    setBusy(true);
    setError("");
    try {
      window.location.href = (await fn()).url;
    } catch (err) {
      setError(err instanceof Error ? err.message : SUPPLIER.errors.generic);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={B.title} description={B.description} />
      <div className="space-y-6">
        {error && <ErrorNote message={error} />}
        {note && <OkNote message={note} />}
        {back &&
          (back.ok ? (
            <OkNote message={back.text} />
          ) : (
            <p role="status" className="rounded-[var(--radius-button)] border border-border px-4 py-3 text-sm text-warn">
              {back.text}
            </p>
          ))}
        {view && (
          <Panel>
            <h2 className="font-semibold">{B.plans}</h2>
            <p className="mt-1 text-xs text-text-muted">{B.plansNote}</p>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {view.plans.map((p) => {
                const current = p.id === view.plan;
                return (
                  <li key={p.id} className={`rounded-[var(--radius-card)] border p-4 ${current ? "border-accent" : "border-border"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{p.name}</p>
                      {current && <Badge tone="good">{B.current}</Badge>}
                    </div>
                    <p className="mt-2 text-sm text-text-secondary">{fill(B.commission, { pct: (p.commission_bp / 100).toString() })}</p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {p.monthly_fee ? `${formatMoney(p.monthly_fee)} ${B.perMonth}` : B.noFee}
                    </p>
                    {!current && (
                      <Button className="mt-3" size="sm" variant="secondary" disabled={busy} onClick={() => void choose(p.id)}>
                        {B.choose}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
            {view.subscription?.status === "pending" && <p className="mt-3 text-sm text-warn">{view.subscription.detail ?? B.pending}</p>}
          </Panel>
        )}

        {view && (
          <Panel>
            <h2 className="font-semibold">{B.payouts}</h2>
            <p className="mt-1 text-sm text-text-secondary">{B.payoutsText}</p>
            {!view.payouts.payments_enabled && <p className="mt-2 text-sm text-text-muted">{B.paymentsOff}</p>}
            {view.payouts.ready ? (
              <p className="mt-3 text-sm text-emerald-300">{B.connected}</p>
            ) : (
              <Button className="mt-3" size="sm" disabled={busy || !view.verified} onClick={() => void open(supplierApi.connectPayouts)}>
                {view.payouts.connected ? B.reconnect : B.connect}
              </Button>
            )}
          </Panel>
        )}

        {statements && (
          <Panel>
            <h2 className="font-semibold">{B.statements}</h2>
            {statements.statements.length === 0 ? (
              <p className="mt-2 text-sm text-text-muted">{B.noStatements}</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-text-muted">
                    <tr>
                      <th className="px-2 py-2 font-medium">{B.month}</th>
                      <th className="px-2 py-2 text-right font-medium">{B.orders}</th>
                      <th className="px-2 py-2 text-right font-medium">{B.commissionCol}</th>
                      <th className="px-2 py-2 text-right font-medium">{B.fee}</th>
                      <th className="px-2 py-2 text-right font-medium">{B.total}</th>
                      <th className="px-2 py-2 font-medium">{B.state}</th>
                      <th className="px-2 py-2 font-medium">{B.invoice}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statements.statements.map((s) => (
                      <tr key={s.statement_id} className="border-t border-border">
                        <td className="px-2 py-2">{s.month}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{s.orders}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{formatMoney(s.commission)}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{formatMoney(s.listing_fee)}</td>
                        <td className="px-2 py-2 text-right font-semibold tabular-nums">{formatMoney(s.total)}</td>
                        <td className="px-2 py-2">{B.statementStates[s.state] ?? s.state}</td>
                        <td className="px-2 py-2">
                          {s.invoice_available ? (
                            <button type="button" disabled={busy} onClick={() => void open(() => supplierApi.invoice(s.statement_id))} className="text-accent hover:underline">
                              PDF
                            </button>
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
        )}
      </div>
    </>
  );
}

export default function BillingPage() {
  return (
    <Suspense fallback={<p className="text-text-muted">…</p>}>
      <BillingInner />
    </Suspense>
  );
}
