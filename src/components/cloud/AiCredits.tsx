"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Check } from "lucide-react";
import { ErrorNote, Panel } from "@/components/dashboard/DashboardShell";
import { UsageMeter } from "@/components/dashboard/UsageMeter";
import { Button } from "@/components/ui/Button";
import {
  aiError,
  formatCredits,
  getAiAccount,
  startTopUp,
  type AiAccount,
  type AiBalance,
  type AiTurn,
} from "@/lib/ai";
import { formatDate } from "@/lib/api";
import { fill } from "@/lib/catalogue";
import { CLOUD_AI } from "@/lib/constants";
import { formatMoney, refreshPayment } from "@/lib/developer";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

/** The section's anchor: the API's `top_up_url` is /dashboard/cloud/#ai-credits. */
const ANCHOR = "ai-credits";
const RECENT_TOP_UPS = 5;

function Balance({ balance }: { balance: AiBalance }) {
  const limit = balance.allowance_monthly;
  return (
    <Panel>
      <h2 className="font-semibold">{CLOUD_AI.title}</h2>
      <div className="mt-4 grid gap-6 md:grid-cols-2">
        <div>
          <p className="text-sm text-text-muted">{CLOUD_AI.balance.left}</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums text-text-primary">
            {balance.credits_remaining === null
              ? CLOUD_AI.balance.unlimited
              : formatCredits(balance.credits_remaining)}
          </p>
          <dl className="mt-4 space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">{CLOUD_AI.balance.topUps}</dt>
              <dd className="tabular-nums text-text-primary">{formatCredits(balance.top_up_remaining)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-text-secondary">{CLOUD_AI.balance.resets}</dt>
              <dd className="text-text-primary">{formatDate(balance.resets_at)}</dd>
            </div>
          </dl>
        </div>
        <div>
          <p className="mb-1 text-sm text-text-muted">{CLOUD_AI.balance.allowance}</p>
          {limit === null ? (
            <p className="text-sm text-text-secondary">{CLOUD_AI.balance.allowanceUnlimited}</p>
          ) : limit === 0 ? (
            <p className="text-sm text-text-secondary">{CLOUD_AI.balance.allowanceNone}</p>
          ) : (
            <UsageMeter
              used={Math.max(limit - balance.allowance_remaining, 0)}
              limit={limit}
              unit={CLOUD_AI.balance.unit}
              label={CLOUD_AI.balance.label}
            />
          )}
        </div>
      </div>
      <p className="mt-4 text-xs text-text-muted">{CLOUD_AI.balance.help}</p>
    </Panel>
  );
}

function BuyCredits({
  account,
  currency,
  switching,
  onCurrency,
}: {
  account: AiAccount;
  /** The currency picked (shown at once; the packs follow when the API answers). */
  currency: string;
  switching: boolean;
  onCurrency: (currency: string) => void;
}) {
  const [packId, setPackId] = useState(account.packs[0]?.id ?? "");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Pack ids are the same in every currency, so the choice survives a switch.
  const pack = account.packs.find((p) => p.id === packId) ?? account.packs[0];
  const recent = account.top_ups.filter((t) => t.state !== "canceled").slice(0, RECENT_TOP_UPS);

  const buy = async () => {
    if (!pack || !consent) return;
    setBusy(true);
    setError("");
    try {
      const { url } = await startTopUp(pack.id, pack.currency);
      window.location.assign(url);
    } catch (err) {
      setError(aiError(err));
      setBusy(false);
    }
  };

  return (
    <Panel>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-semibold">{CLOUD_AI.buy.title}</h2>
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          {CLOUD_AI.buy.currency}
          <select
            value={currency}
            onChange={(e) => onCurrency(e.target.value)}
            disabled={busy}
            className="h-9 rounded-[var(--radius-button)] border border-border bg-background px-2 text-text-primary"
          >
            {account.currencies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      {account.packs.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">{CLOUD_AI.buy.noPacks}</p>
      ) : (
        <div
          role="radiogroup"
          aria-label={CLOUD_AI.buy.packs}
          aria-busy={switching}
          className={cn("mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3", switching && "opacity-60")}
        >
          {account.packs.map((p) => {
            const selected = pack?.id === p.id;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPackId(p.id)}
                className={cn(
                  "rounded-[var(--radius-card)] border bg-background p-4 text-left transition-colors",
                  selected ? "border-accent" : "border-border hover:border-accent/40"
                )}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-text-primary">
                    {fill(CLOUD_AI.buy.pack, { credits: formatCredits(p.credits) })}
                  </span>
                  {selected && <Check size={16} className="text-accent" aria-hidden />}
                </span>
                <span className="mt-3 block text-2xl font-semibold tabular-nums text-text-primary">
                  {formatMoney(p.amount_minor, p.currency)}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-5 max-w-xl space-y-4">
        <p className="text-xs text-text-muted">{CLOUD_AI.buy.tax}</p>
        <label className="flex items-start gap-3 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
          />
          <span>{CLOUD_AI.buy.consent}</span>
        </label>
        <div>
          <Button
            onClick={buy}
            disabled={!consent || busy || switching || !pack}
            className="disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? CLOUD_AI.buy.busy : CLOUD_AI.buy.submit}
          </Button>
          {!consent && <p className="mt-2 text-xs text-text-muted">{CLOUD_AI.buy.reason}</p>}
        </div>
        {error && <ErrorNote message={error} />}
      </div>

      {recent.length > 0 && (
        <div className="mt-6 border-t border-border pt-5">
          <h3 className="text-sm font-medium text-text-secondary">{CLOUD_AI.buy.history}</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {recent.map((t) => (
              <li key={t.reference} className="flex flex-wrap justify-between gap-x-4 gap-y-1">
                <span className="tabular-nums text-text-primary">
                  {fill(CLOUD_AI.buy.pack, { credits: formatCredits(t.credits) })}
                </span>
                <span className={t.state === "credited" ? "text-text-secondary" : "text-warn"}>
                  {CLOUD_AI.buy.states[t.state]}
                  <span className="text-text-muted"> · {timeAgo(t.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}

function Turns({ turns }: { turns: AiTurn[] }) {
  const cols = CLOUD_AI.turns.columns;
  return (
    <Panel>
      <h2 className="font-semibold">{CLOUD_AI.turns.title}</h2>
      {turns.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">{CLOUD_AI.turns.empty}</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="text-left text-xs text-text-muted">
              <tr>
                <th className="pb-2 pr-4 font-medium">{cols.at}</th>
                <th className="pb-2 pr-4 font-medium">{cols.alias}</th>
                <th className="pb-2 pr-4 text-right font-medium">{cols.credits}</th>
                <th className="pb-2 font-medium">{cols.tools}</th>
              </tr>
            </thead>
            <tbody>
              {turns.map((t, i) => (
                <tr key={`${t.at}-${i}`} className="border-t border-border align-top">
                  <td className="whitespace-nowrap py-2 pr-4 text-text-secondary">{timeAgo(t.at)}</td>
                  <td className="py-2 pr-4 font-mono text-xs leading-5 text-text-primary">{t.alias}</td>
                  <td className="py-2 pr-4 text-right tabular-nums text-text-primary">{formatCredits(t.credits)}</td>
                  <td className="py-2 text-text-secondary">
                    {t.tool_names.length ? t.tool_names.join(", ") : CLOUD_AI.turns.noTools}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/**
 * The Cloud page's AI credits: the balance, buying a credit pack, and recent
 * turns. Back from checkout (`?topup=success&ref=…`) it confirms the payment
 * with the provider, as the billing page does. Uses useSearchParams, so the
 * page renders it inside <Suspense> (static export).
 */
export function AiCredits() {
  const params = useSearchParams();
  const topup = params.get("topup");
  const ref = params.get("ref");
  const [account, setAccount] = useState<AiAccount | null>(null);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [notice, setNotice] = useState<string>(() =>
    topup === "canceled"
      ? CLOUD_AI.notices.canceled
      : topup === "success" && ref
        ? CLOUD_AI.notices.confirming
        : ""
  );
  const currency = useRef<string | undefined>(undefined);
  const seq = useRef(0);
  const scrolled = useRef(false);

  // Only the latest request lands (a quick run of currency changes).
  const load = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const data = await getAiAccount(currency.current);
      if (mine !== seq.current) return;
      setAccount(data);
      setError("");
    } catch (err) {
      if (mine !== seq.current) return;
      setError(aiError(err));
      // A currency that didn't load: show the packs already on screen.
      currency.current = undefined;
      setPicked(null);
    } finally {
      if (mine === seq.current) setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Back from checkout: confirm the payment now, in case the provider's
  // webhook is late, then show the new balance.
  useEffect(() => {
    if (topup !== "success" || !ref) return;
    let cancelled = false;
    const attempt = async (n: number): Promise<void> => {
      try {
        const p = await refreshPayment(ref);
        if (cancelled) return;
        if (p.status === "paid") {
          setNotice(CLOUD_AI.notices.added);
        } else if (n < 2) {
          await new Promise((r) => setTimeout(r, 3000 * (n + 1)));
          return attempt(n + 1);
        } else {
          setNotice(CLOUD_AI.notices.processing);
        }
      } catch {
        if (cancelled) return;
        setNotice(CLOUD_AI.notices.unconfirmed);
      }
      void load();
    };
    void attempt(0);
    return () => {
      cancelled = true;
    };
  }, [topup, ref, load]);

  // The section appears after the page's data, so the browser's own jump to
  // #ai-credits (or the return from checkout) has nothing to land on: scroll once.
  useEffect(() => {
    if (!loaded || scrolled.current) return;
    if (!topup && window.location.hash !== `#${ANCHOR}`) return;
    scrolled.current = true;
    document.getElementById(ANCHOR)?.scrollIntoView({ block: "start" });
  }, [loaded, topup]);

  const changeCurrency = (c: string) => {
    currency.current = c;
    setPicked(c);
    void load();
  };

  const shown = picked ?? account?.currency ?? "";

  return (
    <div id={ANCHOR} className="mb-6 scroll-mt-24 space-y-6">
      {notice && (
        <p
          role="status"
          className="rounded-[var(--radius-button)] border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-text-primary"
        >
          {notice}
        </p>
      )}
      {error && <ErrorNote message={error} />}
      {!loaded ? (
        <Panel>
          <h2 className="font-semibold">{CLOUD_AI.title}</h2>
          <p className="mt-4 text-sm text-text-muted">{CLOUD_AI.loading}</p>
        </Panel>
      ) : account && (!account.feature || !account.balance) ? (
        <Panel>
          <h2 className="font-semibold">{CLOUD_AI.title}</h2>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-text-secondary">{CLOUD_AI.locked.text}</p>
            <Button href="/pricing/" variant="secondary" size="sm">
              {CLOUD_AI.locked.cta}
            </Button>
          </div>
        </Panel>
      ) : (
        account?.balance && (
          <>
            <Balance balance={account.balance} />
            <BuyCredits
              account={account}
              currency={shown}
              switching={shown !== account.currency}
              onCurrency={changeCurrency}
            />
            <Turns turns={account.turns} />
          </>
        )
      )}
    </div>
  );
}
