/** The URL is the state (spec 7.1): every page reads its period, accounts and explorer filters
 * from searchParams through these helpers, and every link writes them back the same way.
 * Invalid values fall back to the defaults, so a hand-edited URL never reaches the API as a 422. */

export const PERIODS = ["month", "last_3_months", "ytd", "last_12_months", "custom"] as const;
export type PeriodName = (typeof PERIODS)[number];
export const TX_TYPES = ["expense", "income", "transfer"] as const;
export type TxType = (typeof TX_TYPES)[number];
export const SOURCES = ["rule", "merchant", "jev", "user", "none"] as const;
export type Source = (typeof SOURCES)[number];
export const SAVED = ["unpaired_own", "refunds"] as const;
export type Saved = (typeof SAVED)[number];
export const EXPLORER_KEYS = [
  "q",
  "tx_type",
  "level1",
  "category",
  "merchant_id",
  "is_subscription",
  "category_source",
  "needs_review",
  "saved",
] as const;

export type SearchParams = Record<string, string | string[] | undefined>;

export type Filters = {
  period: PeriodName;
  month?: string; // YYYY-MM; absent = the latest month with data (the API decides)
  start?: string; // YYYY-MM-DD, custom periods only
  end?: string;
  accounts: string[];
};

export type ExplorerFilters = {
  q?: string;
  tx_type?: TxType;
  level1?: string;
  category?: string;
  merchant_id?: string;
  is_subscription?: "true" | "false";
  category_source?: Source;
  needs_review?: "true" | "false";
  saved?: Saved;
};

// The API's bounds: `month` is 1900-01..2099-12, `start` and `end` are 1900-01-01..2100-12-31.
const MONTH = /^(19|20)\d{2}-(0[1-9]|1[0-2])$/;
const FIRST_DAY = "1900-01-01";
const LAST_DAY = "2100-12-31";
const SLUG = /^[a-z0-9_]{1,64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BOOLEANS = ["true", "false"] as const;
const Q_MAX = 100; // GET /transactions: q max_length

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
const all = (value: string | string[] | undefined) => (value === undefined ? [] : [value].flat());

function oneOf<T extends string>(values: readonly T[], value: string | undefined): T | undefined {
  return values.find((item) => item === value);
}

export const isUuid = (value: string | undefined): value is string => value !== undefined && UUID.test(value);
export const isSlug = (value: string | undefined): value is string => value !== undefined && SLUG.test(value);

/** A real calendar day as YYYY-MM-DD within the API's bounds: it refuses 2026-02-30 and 2101-01-01
 * with a 422. */
export function isDay(value: string | undefined): value is string {
  if (value === undefined || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < FIRST_DAY || value > LAST_DAY) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

export function parseFilters(params: SearchParams): Filters {
  const period = oneOf(PERIODS, first(params.period)) ?? "month";
  const accounts = all(params.account_id).filter(isUuid);
  if (period === "custom") {
    const start = first(params.start);
    const end = first(params.end);
    return isDay(start) && isDay(end) && start <= end
      ? { period, start, end, accounts }
      : { period: "month", accounts };
  }
  const month = first(params.month);
  return month !== undefined && MONTH.test(month) ? { period, month, accounts } : { period, accounts };
}

/** The period and account params in a fixed order; the default period is left out. */
export function filterParams(filters: Filters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.period !== "month") params.set("period", filters.period);
  if (filters.month) params.set("month", filters.month);
  if (filters.start) params.set("start", filters.start);
  if (filters.end) params.set("end", filters.end);
  for (const id of filters.accounts) params.append("account_id", id);
  return params;
}

/** A link that keeps the period and accounts, plus page params (undefined leaves one out). */
export function withFilters(path: string, filters: Filters, extra: Record<string, string | undefined> = {}): string {
  const params = filterParams(filters);
  for (const [key, value] of Object.entries(extra)) if (value !== undefined) params.set(key, value);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function parseExplorer(params: SearchParams): ExplorerFilters {
  const q = first(params.q)?.trim().slice(0, Q_MAX);
  const level1 = first(params.level1);
  const category = first(params.category);
  const merchantId = first(params.merchant_id);
  return {
    q: q || undefined,
    tx_type: oneOf(TX_TYPES, first(params.tx_type)),
    level1: isSlug(level1) ? level1 : undefined,
    category: isSlug(category) ? category : undefined,
    merchant_id: isUuid(merchantId) ? merchantId : undefined,
    is_subscription: oneOf(BOOLEANS, first(params.is_subscription)),
    category_source: oneOf(SOURCES, first(params.category_source)),
    needs_review: oneOf(BOOLEANS, first(params.needs_review)),
    saved: oneOf(SAVED, first(params.saved)),
  };
}

/** The explorer's query: the period and accounts, then its filters. The page URL and the API
 * use the same names, so this string serves both. */
export function explorerParams(filters: Filters, explorer: ExplorerFilters): URLSearchParams {
  const params = filterParams(filters);
  for (const [key, value] of Object.entries(explorer)) if (value) params.set(key, value);
  return params;
}

export function toSearchParams(search: URLSearchParams): SearchParams {
  const out: SearchParams = {};
  for (const key of new Set(search.keys())) {
    const values = search.getAll(key);
    out[key] = values.length > 1 ? values : values[0];
  }
  return out;
}

/** The query string with some params replaced; undefined or [] removes a param. */
export function replaceParams(query: string, changes: Record<string, string | string[] | undefined>): string {
  const params = new URLSearchParams(query);
  for (const [key, value] of Object.entries(changes)) {
    params.delete(key);
    for (const item of value === undefined ? [] : [value].flat()) params.append(key, item);
  }
  return params.toString();
}

/** The param changes that select a period; the others (explorer filters, accounts) stay. */
export function periodChanges(choice: Omit<Filters, "accounts">): Record<string, string | undefined> {
  return {
    period: choice.period === "month" ? undefined : choice.period,
    month: choice.month,
    start: choice.start,
    end: choice.end,
  };
}

export function clearedExplorer(query: string): string {
  return replaceParams(query, Object.fromEntries(EXPLORER_KEYS.map((key) => [key, undefined])));
}

/** "2026-01" shifted by -1 is "2025-12" (the "Previous month" preset). */
export function shiftMonth(month: string, months: number): string {
  const [year, index] = month.split("-").map(Number);
  const total = year * 12 + (index - 1) + months;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

/** A merchant page shows spending unless its link asks for income (an employer, say). */
export function detailType(params: SearchParams): "expense" | "income" {
  return first(params.type) === "income" ? "income" : "expense";
}
