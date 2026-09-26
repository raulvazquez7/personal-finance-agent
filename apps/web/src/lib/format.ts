/** Money and dates for display (spec 8: Intl, no date library). Amounts arrive as decimal
 * strings. Days arrive as YYYY-MM-DD and are formatted in UTC, so a browser west of Greenwich
 * never shows the day before. */

import type { Filters } from "./params";

const LOCALE = "en-IE";
const EUR = { style: "currency", currency: "EUR" } as const;
const NO_CENTS = { minimumFractionDigits: 0, maximumFractionDigits: 0 } as const;
const DAY_MS = 86_400_000;

const cents = new Intl.NumberFormat(LOCALE, EUR);
const whole = new Intl.NumberFormat(LOCALE, { ...EUR, ...NO_CENTS });
const signedCents = new Intl.NumberFormat(LOCALE, { ...EUR, signDisplay: "exceptZero" });
const signedWhole = new Intl.NumberFormat(LOCALE, { ...EUR, ...NO_CENTS, signDisplay: "exceptZero" });
const compact = new Intl.NumberFormat(LOCALE, { ...EUR, notation: "compact", maximumFractionDigits: 1 });

type Amount = string | number | null | undefined;

/** The true minus sign. Intl and toFixed write a hyphen-minus; every number on screen, money and
 * deltas alike, shows this one instead. */
export const MINUS = "\u2212";
const minus = (text: string) => text.replace("-", MINUS);

export const toNumber = (value: Amount): number => (value === null || value === undefined ? 0 : Number(value));
export const money = (value: Amount) => minus(cents.format(toNumber(value))); // €2,184.00
export const moneyWhole = (value: Amount) => minus(whole.format(toNumber(value))); // €2,184
/** With an explicit sign, so money in (+€12.34) never reads as money out (−€12.34). */
export const signedMoney = (value: Amount) => minus(signedCents.format(toNumber(value)));
export const signedMoneyWhole = (value: Amount) => minus(signedWhole.format(toNumber(value)));
export const compactMoney = (value: number) => minus(compact.format(value)); // €2.4K, for axis ticks
/** A share under half a percent reads "<1%": a row that is not zero never reads as nothing. */
export const percent = (share: number) => (share > 0 && share < 0.005 ? "<1%" : minus(`${Math.round(share * 100)}%`));
/** The savings rate; empty without income (docs/money-rules.md). */
export const rate = (value: number | null) => (value === null ? "—" : minus(`${(value * 100).toFixed(1)}%`));

const utc = (day: string) => new Date(`${day.slice(0, 10)}T00:00:00Z`);
const dates = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", ...options });
const monthYear = dates({ month: "long", year: "numeric" });
const monthLong = dates({ month: "long" });
const monthAbbr = dates({ month: "short" });
const weekdayDay = dates({ weekday: "short", day: "numeric", month: "short" });
const dayMonth = dates({ day: "numeric", month: "short" });
const dayMonthYear = dates({ day: "numeric", month: "short", year: "numeric" });
const stamp = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" });

export const monthLabel = (month: string) => monthYear.format(utc(`${month}-01`)); // August 2026
export const monthShort = (month: string) => monthAbbr.format(utc(`${month}-01`)); // Aug
export const dayHeader = (day: string) => weekdayDay.format(utc(day)); // Sat, 1 Aug
export const dayShort = (day: string) => dayMonth.format(utc(day)); // 1 Aug
export const dayLong = (day: string) => dayMonthYear.format(utc(day)); // 1 Aug 2026
/** An import's timestamp, in the reader's own time zone. */
export const dateTime = (iso: string) => stamp.format(new Date(iso));

/** The day `offset` days after `start`: the cumulative charts label day N of a period. */
export const dayAt = (start: string, offset: number) =>
  new Date(utc(start).getTime() + offset * DAY_MS).toISOString().slice(0, 10);
export const daysIn = (start: string, end: string) =>
  Math.round((utc(end).getTime() - utc(start).getTime()) / DAY_MS) + 1;

/** A range of days, with the start's year only when it spans two years: "10 Aug – 19 Aug 2026",
 * "10 Dec 2025 – 19 Jan 2026". */
export const dayRange = (start: string, end: string) =>
  `${start.slice(0, 4) === end.slice(0, 4) ? dayShort(start) : dayLong(start)} – ${dayLong(end)}`;

/** The fields of Schemas["PeriodOut"] these labels need. */
export type PeriodLike = { name: string; start: string; end: string; previous_start: string; previous_end: string };

/** The period pill: "August 2026", "Last 3 months", "10 Aug – 19 Aug 2026". */
export function periodLabel(filters: Filters, latestDay: string | null): string {
  switch (filters.period) {
    case "month": {
      const month = filters.month ?? latestDay?.slice(0, 7);
      return month ? monthLabel(month) : "Latest month";
    }
    case "last_3_months":
      return "Last 3 months";
    case "last_12_months":
      return "Last 12 months";
    case "ytd":
      return "Year to date";
    case "custom":
      return dayRange(filters.start!, filters.end!);
  }
}

/** A page's resolved period: "August 2026" or "1 Jun – 31 Aug 2026". */
export function rangeLabel(period: PeriodLike): string {
  return period.name === "month" ? monthLabel(period.start.slice(0, 7)) : dayRange(period.start, period.end);
}

/** What a delta compares with (spec 2.6: the previous period of the same length). */
export function previousLabel(period: PeriodLike, style: "short" | "long" = "short"): string {
  if (period.name === "month") return `vs ${(style === "short" ? monthAbbr : monthLong).format(utc(period.previous_start))}`;
  if (period.name === "last_3_months") return "vs the 3 months before";
  if (period.name === "last_12_months") return "vs the 12 months before";
  if (period.name === "ytd") return "vs the same dates last year";
  // The whole range before: it ends the day before this one starts. `previous_end` can come
  // earlier, when the data ends inside the period (the API then compares as many days).
  return `vs the ${daysIn(period.previous_start, dayAt(period.start, -1))} days before`;
}

/** The two series of a cumulative chart: "August" and "July", or this and the previous period. */
export function periodNames(period: PeriodLike): { current: string; previous: string } {
  if (period.name !== "month") return { current: "This period", previous: "Previous period" };
  return { current: monthLong.format(utc(period.start)), previous: monthLong.format(utc(period.previous_start)) };
}
