import { describe, expect, it } from "vitest";

import {
  clearedExplorer,
  detailType,
  explorerParams,
  filterParams,
  isDay,
  parseExplorer,
  parseFilters,
  replaceParams,
  shiftMonth,
  toSearchParams,
  withFilters,
} from "./params";

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

describe("parseFilters", () => {
  it("defaults to the latest month and all accounts", () => {
    expect(parseFilters({})).toEqual({ period: "month", accounts: [] });
  });

  it("keeps valid values and repeated accounts", () => {
    expect(parseFilters({ period: "last_3_months", month: "2026-08", account_id: [A, B] })).toEqual({
      period: "last_3_months",
      month: "2026-08",
      accounts: [A, B],
    });
  });

  it("drops what the API would refuse", () => {
    expect(parseFilters({ period: "week", month: "2026-13", account_id: ["1; drop", A] })).toEqual({
      period: "month",
      accounts: [A],
    });
    // GET /dashboard/overview and friends take months 1900-01..2099-12 only.
    expect(parseFilters({ month: "2100-01" })).toEqual({ period: "month", accounts: [] });
  });

  it("keeps a custom range only when it is two real days in order", () => {
    expect(parseFilters({ period: "custom", start: "2026-08-10", end: "2026-08-19" })).toEqual({
      period: "custom",
      start: "2026-08-10",
      end: "2026-08-19",
      accounts: [],
    });
    expect(parseFilters({ period: "custom", start: "2026-08-19", end: "2026-08-10" }).period).toBe("month");
    expect(parseFilters({ period: "custom", start: "2026-02-01", end: "2026-02-30" }).period).toBe("month");
    expect(parseFilters({ period: "custom", start: "1899-12-31", end: "2026-08-10" }).period).toBe("month");
  });
});

describe("links carry the filters", () => {
  const august = { period: "month" as const, month: "2026-08", accounts: [A] };

  it("writes the period and accounts in a fixed order and leaves the default out", () => {
    expect(withFilters("/spending/shopping", august)).toBe(`/spending/shopping?month=2026-08&account_id=${A}`);
    expect(withFilters("/", { period: "month", accounts: [] })).toBe("/");
    expect(withFilters("/transactions", august, { level1: "shopping", q: undefined })).toBe(
      `/transactions?month=2026-08&account_id=${A}&level1=shopping`,
    );
  });

  it("round-trips through a URL", () => {
    const custom = { period: "custom" as const, start: "2026-08-10", end: "2026-08-19", accounts: [A, B] };
    expect(parseFilters(toSearchParams(filterParams(custom)))).toEqual(custom);
  });
});

describe("explorer filters", () => {
  it("keeps known values, trims the search and cuts it to the API limit", () => {
    const explorer = parseExplorer({
      q: `  ${"x".repeat(150)} `,
      tx_type: "expense",
      level1: "shopping",
      category_source: "jev",
      saved: "refunds",
      needs_review: "true",
    });
    expect(explorer.q).toHaveLength(100);
    expect(explorer).toMatchObject({
      tx_type: "expense",
      level1: "shopping",
      category_source: "jev",
      saved: "refunds",
      needs_review: "true",
    });
  });

  it("drops unknown values", () => {
    expect(
      parseExplorer({ tx_type: "loan", category: "Robert'); DROP", merchant_id: "42", is_subscription: "maybe", q: "  " }),
    ).toEqual({});
  });

  it("adds the explorer filters after the period and clears them again", () => {
    const query = explorerParams({ period: "ytd", accounts: [] }, { q: "zztest", tx_type: "expense" }).toString();
    expect(query).toBe("period=ytd&q=zztest&tx_type=expense");
    expect(clearedExplorer(query)).toBe("period=ytd");
  });
});

describe("query helpers", () => {
  it("replaces and removes params", () => {
    expect(replaceParams(`period=ytd&account_id=${A}&q=zztest`, { period: undefined, month: "2026-07", q: undefined })).toBe(
      `account_id=${A}&month=2026-07`,
    );
    expect(replaceParams("", { account_id: [A, B] })).toBe(`account_id=${A}&account_id=${B}`);
  });

  it("shifts months across a year", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2025-12", 1)).toBe("2026-01");
  });

  it("knows a real day and the detail page type", () => {
    expect(isDay("2028-02-29")).toBe(true);
    expect(isDay("2026-02-29")).toBe(false);
    expect(isDay("2101-01-01")).toBe(false);
    expect(detailType({ type: "income" })).toBe("income");
    expect(detailType({ type: "loan" })).toBe("expense");
  });
});
