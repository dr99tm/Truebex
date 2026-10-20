// PF7e: the orders page opened from an order's link (contract marketplace-api
// 1.2.0 `web_url`, the app's "Open on the web"):
// /dashboard/orders/?order=<order id>. The static export cannot serve a page
// per order, so the id is read on the client: the page shows that order first
// and highlighted, asks 5.9 for it when it is not on 5.8's first page, and
// says so when the account has no such order (an unknown id, another
// account's order, or a malformed link).
import type { MarketOrder } from "@/lib/market";

export const ORDER_ID = /^[0-9a-f]{32}$/;

/** The order id a `?order=` value names (any case), or null when it names none. */
export function linkedOrderId(value: string | null | undefined): string | null {
  const id = (value ?? "").trim().toLowerCase();
  return ORDER_ID.test(id) ? id : null;
}

/** The id the page asks 5.9 for: a well-formed link to an order not in this list. */
export function linkedOrderToFetch(orders: MarketOrder[], link: string | null | undefined): string | null {
  const id = linkedOrderId(link);
  return id && !orders.some((o) => o.order_id === id) ? id : null;
}

export interface OrderLinkView {
  /** The orders to show, the linked one first. */
  orders: MarketOrder[];
  /** The linked order's id once it is shown, else null. */
  focused: string | null;
  /** True when the link names no order of this account. */
  note: boolean;
}

/**
 * What the orders page shows for 5.8's `orders` and the `?order=` value.
 * `fetched` is 5.9's answer for a linked order that is not in the list:
 * `undefined` while not asked (or still loading), `null` when 5.9 answered
 * 404 or 403 (no such order in this account).
 */
export function orderLinkView(
  orders: MarketOrder[],
  link: string | null | undefined,
  fetched?: MarketOrder | null
): OrderLinkView {
  if (link == null || link === "") return { orders, focused: null, note: false };
  const id = linkedOrderId(link);
  if (!id) return { orders, focused: null, note: true };
  const listed = orders.find((o) => o.order_id === id);
  const linked = listed ?? (fetched && fetched.order_id === id ? fetched : null);
  if (!linked) return { orders, focused: null, note: fetched === null };
  return { orders: [linked, ...orders.filter((o) => o.order_id !== id)], focused: id, note: false };
}
