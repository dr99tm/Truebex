"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ApiError, getToken } from "@/lib/api";
import { fetchMe } from "@/lib/auth";
import {
  DEFAULT_VARIANT,
  MAX_ITEMS,
  basketQuery,
  canOrder,
  newIdempotencyKey,
  orderLines,
  parseBasket,
  totalsByCurrency,
  variantLabel,
  type BasketItem,
  type ItemRef,
  type TotalLine,
} from "@/lib/basket";
import {
  describeBasket,
  marketRegions,
  placeBasketOrder,
  priceBasket,
  type DescribedLine,
  type PricedLine,
  type Region,
  type Substitute,
} from "@/lib/basket-api";
import { MARKET_BASKET } from "@/lib/constants";
import { formatMoney } from "@/lib/market";

const B = MARKET_BASKET;

const fill = (text: string, values: Record<string, string | number>) =>
  text.replace(/\{(\w+)\}/g, (whole, key: string) => (key in values ? String(values[key]) : whole));

const errorText = (err: unknown) => (err instanceof Error && err.message ? err.message : B.failed);

const inputClass =
  "w-full rounded-[var(--radius-button)] border border-border bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-accent/50";

type Reason = "notFound" | "variantNotFound" | "withdrawn" | "notSold" | "noPrice" | "unavailable";

interface Line {
  index: number;
  /** What was priced: the link's item, its `default` resolved, or the person's choice. */
  ref: BasketItem;
  described: DescribedLine;
  priced: PricedLine;
  reason: Reason | null;
}

function reasonOf(d: DescribedLine, p: PricedLine): Reason | null {
  if (d.status === "not_found" || p.status === "not_found") return d.name ? "variantNotFound" : "notFound";
  if (d.status === "withdrawn" || p.status === "withdrawn") return "withdrawn";
  if (p.status === "not_sold_in_region") return "notSold";
  if (!p.price) return "noPrice";
  if (!canOrder(p.availability?.state)) return "unavailable";
  return null;
}

interface Contact {
  name: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  postcode: string;
  message: string;
}

// The "Buy this look" basket (contract marketplace-api §3, PR2): the app opens
// /market/basket/?region=<r>&items=<supplier>:<sku>:<variant>:<qty>,... with a
// room theme's products. The page names and prices every line for the region
// (POST /market/basket, then 5.5), totals what can be ordered per currency,
// and sends it through PF7's flow: sign in, 5.7 with an Idempotency-Key and
// each line's price_seen, then the checkout page for that order.
export function BasketPanel() {
  const params = useSearchParams();
  const regionParam = params.get("region");
  const itemsParam = params.get("items");
  const parsed = useMemo(() => parseBasket(regionParam, itemsParam), [regionParam, itemsParam]);

  // The person's changes: another version, or a similar product instead (by line).
  const [overrides, setOverrides] = useState<Record<number, ItemRef>>({});
  const refs = useMemo<BasketItem[]>(
    () => parsed.items.map((item, i) => ({ ...item, ...(overrides[i] ?? {}) })),
    [parsed, overrides]
  );

  const [regions, setRegions] = useState<Region[] | null>(null);
  const [lines, setLines] = useState<Line[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [repricing, setRepricing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const region = regions?.find((r) => r.region === parsed.region) ?? null;
  const regionCode = region?.region ?? null;

  useEffect(() => {
    let cancelled = false;
    marketRegions()
      .then((answer) => {
        if (cancelled) return;
        setRegions(answer.regions);
        setLoadError("");
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorText(err));
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(() => {
    if (!regionCode || !refs.length) return;
    let cancelled = false;
    async function load(code: string) {
      try {
        const described = (await describeBasket(code, refs)).items;
        const toPrice = refs.map((r, i) => ({ ...r, variant_id: described[i].variant?.variant_id ?? r.variant_id }));
        const priced = (await priceBasket(code, toPrice)).items;
        if (cancelled) return;
        setLines(
          toPrice.map((ref, i) => ({ index: i, ref, described: described[i], priced: priced[i], reason: reasonOf(described[i], priced[i]) }))
        );
        setLoadError("");
      } catch (err) {
        if (!cancelled) setLoadError(errorText(err));
      } finally {
        if (!cancelled) setRepricing(false);
      }
    }
    void load(regionCode);
    return () => {
      cancelled = true;
    };
  }, [regionCode, refs, attempt]);

  function reprice() {
    setRepricing(true);
    setAttempt((n) => n + 1);
  }

  function replace(index: number, ref: ItemRef) {
    setRepricing(true);
    setOverrides((o) => ({ ...o, [index]: { supplier_id: ref.supplier_id, sku: ref.sku, variant_id: ref.variant_id } }));
  }

  // Where sign-in comes back to: this basket, with the person's choices.
  const returnPath = regionCode ? `/market/basket/${basketQuery(regionCode, refs)}` : `/market/basket/?${params.toString()}`;

  const rejected = parsed.rejected.length > 0 && (
    <div className="mb-6 rounded-[var(--radius-card)] border border-warn/30 bg-warn/5 p-4 text-sm" data-rejected={parsed.rejected.length}>
      <p className="font-medium text-text-primary">{B.rejectedTitle}</p>
      <ul className="mt-2 space-y-1 text-text-secondary">
        {parsed.rejected.map((r) => (
          <li key={r.position}>
            {fill(B.item, { position: r.position })}: {B.rejected[r.reason]}
            <span className="block break-all font-mono text-xs text-text-muted">{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );

  if (parsed.tooMany !== null) {
    return <p className="text-text-secondary" data-basket-state="too-many">{fill(B.tooMany, { count: parsed.tooMany, max: MAX_ITEMS })}</p>;
  }
  if (!parsed.items.length) {
    return (
      <div data-basket-state="empty">
        {rejected}
        <p className="text-text-secondary">{B.empty}</p>
      </div>
    );
  }
  if (!regions || (region && !lines)) {
    return loadError ? (
      <div className="space-y-4" data-basket-state="error">
        <p role="alert" className="text-red-300">{loadError}</p>
        <Button variant="secondary" onClick={reprice}>{B.retry}</Button>
      </div>
    ) : (
      <p className="text-text-muted" role="status" data-basket-state="loading">{B.loading}</p>
    );
  }
  if (!region) {
    return (
      <div data-basket-state="region">
        {rejected}
        <p className="text-text-secondary">
          {parsed.region ? fill(B.regionUnknown, { region: parsed.region }) : B.regionMissing}
        </p>
        <ul className="mt-4 flex flex-wrap gap-3">
          {regions.map((r) => (
            <li key={r.region}>
              <Button variant="secondary" href={`/market/basket/${basketQuery(r.region, parsed.items)}`}>
                {r.name} · {r.currency}
              </Button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const ready = lines ?? [];
  const totalLines: TotalLine[] = ready.map((l) => ({ ref: l.ref, qty: l.ref.qty, price: l.priced.price, included: l.reason === null }));
  const totals = totalsByCurrency(totalLines);
  const included = ready.filter((l) => l.reason === null);
  const kind = included.every((l) => l.described.orderable) ? "order" : "quote";

  return (
    <div data-basket-state={repricing ? "repricing" : "ready"} data-kind={kind}>
      {rejected}
      <p className="text-sm text-text-muted">
        {fill(B.regionLine, { name: region.name, currency: region.currency })}
        {repricing && <span className="ml-2" role="status">{B.repricing}</span>}
      </p>
      <ul className="mt-2 divide-y divide-border">
        {ready.map((l) => (
          <BasketRow key={l.index} line={l} region={region} onReplace={(ref) => replace(l.index, ref)} disabled={repricing} />
        ))}
      </ul>

      <div className="mt-2 space-y-2 border-t border-border pt-4">
        {totals.length ? (
          totals.map((t) => (
            <div key={t.currency} className="flex items-baseline justify-between">
              <span className="text-lg font-semibold text-text-primary">{B.total}</span>
              <span className="text-2xl font-bold tabular-nums text-text-primary" data-total={t.amount} data-currency={t.currency}>
                {formatMoney(t)}
              </span>
            </div>
          ))
        ) : (
          <p className="text-text-secondary" data-total="none">{fill(B.nothingToOrder, { region: region.name })}</p>
        )}
        {totals.length > 0 && (
          <p className="text-xs text-text-muted">
            {fill(region.tax.prices_include_tax ? B.taxIncluded : B.taxAdded, { tax: region.tax.name })} {B.deliveryNote}
          </p>
        )}
      </div>
      {loadError && <p role="alert" className="mt-4 text-sm text-red-300">{loadError}</p>}

      {included.length > 0 && (
        <OrderForm
          region={region}
          kind={kind}
          lines={totalLines}
          returnPath={returnPath}
          busy={repricing}
          onStale={reprice}
        />
      )}
    </div>
  );
}

function BasketRow({
  line,
  region,
  onReplace,
  disabled,
}: {
  line: Line;
  region: Region;
  onReplace: (ref: ItemRef) => void;
  disabled: boolean;
}) {
  const { described: d, priced: p, ref, reason } = line;
  const price = p.price;
  const state = p.availability?.state;
  // An unknown line keeps the link's version, unless it is the app's `default` placeholder.
  const version = d.variant
    ? variantLabel(d.variant.options) || d.variant.variant_id
    : ref.variant_id === DEFAULT_VARIANT
      ? null
      : ref.variant_id;
  return (
    <li className="py-4" data-line-state={reason ?? "ok"} data-sku={ref.sku}>
      <div className="flex gap-4">
        {d.thumbnail_url && (
          // eslint-disable-next-line @next/next/no-img-element -- API-served thumbnail, static export
          <img src={d.thumbnail_url} alt={d.name ?? ref.sku} width={64} height={64} loading="lazy" className="h-16 w-16 shrink-0 rounded object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-medium text-text-primary">{d.name ?? ref.sku}</p>
            {reason === null && price && (
              <p className="font-medium tabular-nums text-text-primary">{formatMoney({ ...price, amount: price.amount * ref.qty })}</p>
            )}
          </div>
          <p className="text-sm text-text-muted">
            {[d.supplier_name, version].filter(Boolean).join(" · ")}
          </p>
          <p className="text-sm text-text-secondary">
            {B.qty} {ref.qty}
            {price && ` × ${formatMoney(price)} ${B.each}`}
            {state && (
              <span className={state === "in_stock" || state === "low_stock" || state === "made_to_order" ? "ml-2 text-emerald-300" : "ml-2 text-warn"}>
                {B.states[state] ?? state}
                {state === "made_to_order" && p.availability?.lead_time_days != null &&
                  ` · ${fill(B.leadTime, { days: p.availability.lead_time_days })}`}
              </span>
            )}
          </p>
          {reason && <p className="mt-1 text-sm text-warn">{fill(B.reasons[reason], { region: region.name })}</p>}

          {d.variants && d.variants.length > 1 && (
            <label className="mt-2 block text-sm text-text-secondary">
              {d.variant?.resolved === "first" && <span className="block text-xs text-text-muted">{fill(B.versionChosen, { count: d.variants.length })}</span>}
              <span className="mr-2">{B.version}</span>
              <select
                value={ref.variant_id}
                disabled={disabled}
                onChange={(e) => onReplace({ supplier_id: ref.supplier_id, sku: ref.sku, variant_id: e.target.value })}
                className="rounded-[var(--radius-button)] border border-border bg-surface px-2 py-1 text-text-primary"
              >
                {d.variants.map((v) => (
                  <option key={v.variant_id} value={v.variant_id}>
                    {variantLabel(v.options) || v.variant_id}
                  </option>
                ))}
              </select>
            </label>
          )}

          {p.substitutes.length > 0 && (
            <div className="mt-3 rounded-[var(--radius-card)] border border-border bg-background/40 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-text-muted">{B.substitutes}</p>
              <ul className="mt-2 space-y-2">
                {p.substitutes.map((s: Substitute) => (
                  <li key={`${s.supplier_id}/${s.sku}/${s.variant_id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="min-w-0 text-text-primary">
                      {s.name}
                      <span className="text-text-muted">
                        {s.supplier_name ? ` · ${s.supplier_name}` : ""}
                        {s.price ? ` · ${formatMoney(s.price)}` : ""}
                      </span>
                    </span>
                    <Button size="sm" variant="secondary" disabled={disabled} onClick={() => onReplace(s)}>
                      {B.useInstead}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function OrderForm({
  region,
  kind,
  lines,
  returnPath,
  busy,
  onStale,
}: {
  region: Region;
  kind: "order" | "quote";
  lines: TotalLine[];
  returnPath: string;
  busy: boolean;
  onStale: () => void;
}) {
  const [signedIn, setSignedIn] = useState(() => !!getToken());
  const [contact, setContact] = useState<Contact>({ name: "", email: "", phone: "", address: "", city: "", postcode: "", message: "" });
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  // One key per attempt: a retried click (network error) replays the first order.
  const idempotencyKey = useRef("");

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        if (!me) setSignedIn(false);
        else setContact((c) => ({ ...c, name: c.name || me.name || "", email: c.email || me.email }));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  const field = (key: keyof Contact) => ({
    value: contact[key],
    onChange: (e: { target: { value: string } }) => setContact((c) => ({ ...c, [key]: e.target.value })),
    className: inputClass,
  });

  async function send(e: FormEvent) {
    e.preventDefault();
    setSending(true);
    setNotice("");
    setError("");
    idempotencyKey.current ||= newIdempotencyKey();
    try {
      const order = await placeBasketOrder(
        {
          kind,
          region: region.region,
          contact: {
            name: contact.name.trim(),
            email: contact.email.trim(),
            phone: contact.phone.trim() || null,
            message: contact.message.trim() || null,
          },
          delivery: {
            country: region.region.split("-")[0],
            city: contact.city.trim(),
            postcode: contact.postcode.trim() || null,
            address: contact.address.trim(),
          },
          lines: orderLines(lines),
        },
        idempotencyKey.current
      );
      window.location.href = `/market/checkout/?order=${order.order_id}`;
      return;
    } catch (err) {
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) idempotencyKey.current = "";
      if (err instanceof ApiError && err.status === 401) setSignedIn(false);
      else if (err instanceof ApiError && ["price_changed", "unavailable", "region_not_served"].includes(err.code)) {
        // The server priced the lines again: show the basket as it is now and ask again.
        setNotice(err.code === "price_changed" ? B.priceChanged : err.message);
        onStale();
      } else setError(errorText(err));
    }
    setSending(false);
  }

  return (
    <section aria-labelledby="basket-order" className="mt-10 border-t border-border pt-6">
      <h2 id="basket-order" className="text-xl font-semibold text-text-primary">
        {B.orderTitle}
      </h2>
      {notice && (
        <p className="mt-3 rounded-[var(--radius-button)] border border-warn/30 bg-warn/5 px-4 py-3 text-sm text-text-primary" role="status">
          {notice}
        </p>
      )}
      {!signedIn ? (
        <div className="mt-3 space-y-4" data-signin>
          <p className="text-text-secondary">{B.signInText}</p>
          <div className="flex flex-wrap gap-3">
            <Button href={`/login/?next=${encodeURIComponent(returnPath)}`}>{B.signIn}</Button>
            <Button variant="secondary" href={`/signup/?next=${encodeURIComponent(returnPath)}`}>
              {B.createAccount}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={send} className="mt-4 grid gap-4 sm:grid-cols-2">
          <input aria-label={B.name} placeholder={B.name} autoComplete="name" required maxLength={120} {...field("name")} />
          <input type="email" aria-label={B.email} placeholder={B.email} autoComplete="email" required {...field("email")} />
          <input aria-label={B.address} placeholder={B.address} autoComplete="street-address" required maxLength={300} {...field("address")} className={`${inputClass} sm:col-span-2`} />
          <input aria-label={B.city} placeholder={B.city} autoComplete="address-level2" required maxLength={120} {...field("city")} />
          <input aria-label={B.postcode} placeholder={B.postcode} autoComplete="postal-code" maxLength={20} {...field("postcode")} />
          <input type="tel" aria-label={B.phone} placeholder={B.phone} autoComplete="tel" maxLength={40} {...field("phone")} />
          <p className="self-center text-sm text-text-secondary">{fill(B.deliveryTo, { name: region.name })}</p>
          <textarea aria-label={B.message} placeholder={B.message} rows={3} maxLength={2000} {...field("message")} className={`${inputClass} sm:col-span-2`} />
          {kind === "quote" && <p className="text-sm text-text-secondary sm:col-span-2">{B.quoteOnly}</p>}
          <div className="space-y-2 sm:col-span-2">
            <Button type="submit" size="lg" disabled={sending || busy}>
              {sending ? B.sending : kind === "order" ? B.placeOrder : B.requestQuote}
            </Button>
            {kind === "order" && <p className="text-xs text-text-muted">{B.orderNext}</p>}
          </div>
        </form>
      )}
      {error && (
        <p role="alert" className="mt-4 rounded-[var(--radius-button)] border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}
