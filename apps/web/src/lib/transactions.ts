/** The explorer's rows: grouped by day (spec 7.3). */

import type { Schemas } from "./api";

type Tx = Schemas["Transaction"];
type Category = Schemas["CategoryOut"];

export type Day = { day: string; net: number; items: Tx[] };

/** Rows arrive newest first (booked_at desc). A day split across two "Load more" pages still gets
 * one header, because the pages are grouped together after they are merged. */
export function groupByDay(items: Tx[]): Day[] {
  const days: Day[] = [];
  for (const tx of items) {
    const last = days.at(-1);
    if (last && last.day === tx.booked_at) {
      last.items.push(tx);
      last.net += Number(tx.amount);
    } else {
      days.push({ day: tx.booked_at, net: Number(tx.amount), items: [tx] });
    }
  }
  return days;
}

/** What the side panel saved (spec 7.3). `categorySlug` is null when only the note changed;
 * `merchant` is set when the merchant changed; `defaultFor` is the merchant whose default the
 * change became ("Apply to all transactions of this merchant?" → yes). `isSubscription` is null
 * when that default came from money in, which has no subscription switch: every row keeps its own. */
export type LabelChange = {
  id: string;
  categorySlug: string | null;
  isSubscription: boolean | null;
  merchant: { id: string | null; name: string } | null;
  note: string | null;
  defaultFor: string | null;
};

// labels._RELABEL_MERCHANT in the API: a merchant default relabels these sources only, so the
// user's own labels and the system rules keep theirs, and it never gives money going out an
// income category (those rows keep theirs too).
const FOLLOW_THE_MERCHANT = ["jev", "merchant", "none"];

/** The loaded rows after a save, patched in place so "Load more" pages are not lost. */
export function applyChange(rows: Tx[], change: LabelChange, categories: Category[]): Tx[] {
  const category = categories.find((c) => c.slug === change.categorySlug);
  const labelled = (row: Tx, source: Tx["category_source"]): Tx =>
    category
      ? {
          ...row,
          category_slug: category.slug,
          level1: category.level1,
          // CategoryOut.tx_type is a plain string; Transaction.tx_type is typed.
          tx_type: category.tx_type as Tx["tx_type"],
          category_source: source,
          needs_review: false,
          // Only money going out is a subscription (spec 6), as in labels._SUBSCRIPTION.
          is_subscription: (change.isSubscription ?? row.is_subscription) && category.tx_type === "expense" && Number(row.amount) < 0,
        }
      : row;
  return rows.map((row) => {
    if (row.id === change.id) {
      // A new merchant's id comes back only on reload, so it stays null here.
      const merchant = change.merchant ? { merchant_id: change.merchant.id, merchant_name: change.merchant.name } : {};
      return { ...labelled(row, "user"), ...merchant, note: change.note };
    }
    const fits = !(Number(row.amount) < 0 && category?.tx_type === "income");
    if (change.defaultFor && row.merchant_id === change.defaultFor && FOLLOW_THE_MERCHANT.includes(row.category_source) && fits) {
      return labelled(row, "merchant");
    }
    return row;
  });
}
