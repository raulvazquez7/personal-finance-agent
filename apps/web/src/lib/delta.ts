/** Changes against the previous period (spec 2.6): hidden when the previous period has no data,
 * "new" when the previous value was 0, and a tone that says whether the change is good. The
 * arrow and the sign carry the meaning, so it never depends on colour alone. */

import { MINUS } from "./format";

export type Good = "up" | "down";
export type Unit = "percent" | "euro" | "points";
export type Tone = "good" | "bad" | "neutral";
export type Delta =
  | { kind: "hidden" }
  | { kind: "new" }
  | { kind: "change"; direction: "up" | "down" | "flat"; tone: Tone; text: string };

const euro = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const flat = (text: string): Delta => ({ kind: "change", direction: "flat", tone: "neutral", text });

/** `good` says which way is good: less spending, more income, more savings, a higher rate.
 * Rates are fractions (0.328), so "points" moves them by 100. */
export function delta(current: number | null, previous: number | null | undefined, good: Good, unit: Unit): Delta {
  if (current === null || previous === null || previous === undefined) return { kind: "hidden" };
  let change: number;
  let text: string;
  if (unit === "percent") {
    if (previous === 0) return current === 0 ? flat("0%") : { kind: "new" };
    change = Math.round(((current - previous) / Math.abs(previous)) * 100);
    // −100% means "down to nothing": an amount that is not zero stops at −99%.
    if (change === -100 && current !== 0) change = -99;
    text = `${Math.abs(change)}%`;
  } else if (unit === "euro") {
    change = Math.round(current - previous);
    text = euro.format(Math.abs(change));
  } else {
    change = Math.round((current - previous) * 100);
    text = `${Math.abs(change)} pts`;
  }
  if (change === 0) return flat(text);
  const direction = change > 0 ? "up" : "down";
  return { kind: "change", direction, tone: direction === good ? "good" : "bad", text: `${change > 0 ? "+" : MINUS}${text}` };
}

type Cumulative = { current: { total: string }[]; previous: { total: string }[] | null };

/** "Spent so far against the previous period at the same day" (spec 7.1). The current series
 * stops at the latest imported day, and is empty when the period has no data yet: that reads as
 * no data, never 0 (spec 2.6). The previous one is read at the same day, or at its end when it
 * is shorter (February against January). */
export function atSameDay(cumulative: Cumulative): { current: number | null; previous: number | null } {
  const index = cumulative.current.length - 1;
  if (index < 0) return { current: null, previous: null };
  const current = Number(cumulative.current[index].total);
  const before = cumulative.previous;
  if (!before || before.length === 0) return { current, previous: null };
  return { current, previous: Number(before[Math.min(index, before.length - 1)].total) };
}

type MonthFlag = { month: string; has_data: boolean };

/** Whether any month of the period has data (spec 2.6: a month has data when at least one
 * transaction of the selected accounts is booked in it). Without data, the KPI tiles read "—",
 * never 0 (Decision G). The series holds the 12 months that end with the period, so a longer
 * custom range cannot be judged from it: the API's numbers stand. */
export function periodHasData(months: MonthFlag[], period: { start: string; end: string }): boolean {
  const from = period.start.slice(0, 7);
  const to = period.end.slice(0, 7);
  if (months.length === 0 || from < months[0].month) return true;
  return months.some((point) => point.has_data && point.month >= from && point.month <= to);
}
