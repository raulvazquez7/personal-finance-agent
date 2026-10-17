import type { Schemas } from "./api";

type Item = Schemas["ReviewItem"];
export type ReviewFilter = "all" | "categories" | "duplicates";
export type ReviewSort = "amount" | "date";

const isMerge = (item: Item) => item.kind === "merge";
const latestDay = (item: Item) => item.transactions.reduce((day, t) => (t.booked_at > day ? t.booked_at : day), "");

const ORDER: Record<ReviewSort, (a: Item, b: Item) => number> = {
  amount: (a, b) => Math.abs(Number(b.total)) - Math.abs(Number(a.total)),
  date: (a, b) => latestDay(b).localeCompare(latestDay(a)),
};

/** The cards /review shows (spec 9): category cards in the chosen order, then merge cards, most
 * confident first; skipped cards go to the end in the order they were skipped. */
export function reviewOrder(items: Item[], filter: ReviewFilter, sort: ReviewSort, skipped: string[]): Item[] {
  const shown = items.filter((item) => filter === "all" || isMerge(item) === (filter === "duplicates"));
  const sorted = shown.sort(
    (a, b) =>
      Number(isMerge(a)) - Number(isMerge(b)) ||
      (isMerge(a) ? (b.merge?.confidence ?? 0) - (a.merge?.confidence ?? 0) : ORDER[sort](a, b)) ||
      a.key.localeCompare(b.key),
  );
  const rank = (item: Item) => skipped.indexOf(item.key);
  return [
    ...sorted.filter((item) => rank(item) < 0),
    ...sorted.filter((item) => rank(item) >= 0).sort((a, b) => rank(a) - rank(b)),
  ];
}
