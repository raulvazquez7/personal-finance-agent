import { describe, expect, it } from "vitest";

import {
  buildYear,
  mergeSpans,
  missingSummary,
  monthSpan,
  monthState,
  yearBounds,
  type AccountRef,
  type ImportSpan,
} from "./coverage";

const TODAY = "2026-10-17";
const span = (start: string, end: string) => ({ start, end });
const row = (accountId: string, start: string | null, end: string | null): ImportSpan => ({ accountId, start, end });
const august = monthSpan("2026-08");
const ACCOUNTS: AccountRef[] = [
  { id: "b", name: "ZZTEST Savings", digits: "····0002" },
  { id: "a", name: "ZZTEST Everyday", digits: null },
];

describe("monthSpan", () => {
  it("runs from the first to the last day, leap years included", () => {
    expect(monthSpan("2026-08")).toEqual(span("2026-08-01", "2026-08-31"));
    expect(monthSpan("2028-02")).toEqual(span("2028-02-01", "2028-02-29"));
    expect(monthSpan("2026-12")).toEqual(span("2026-12-01", "2026-12-31"));
  });
});

describe("mergeSpans", () => {
  it("joins spans that touch or overlap, and keeps a hole", () => {
    expect(
      mergeSpans([
        span("2026-08-06", "2026-08-08"),
        span("2026-08-01", "2026-08-05"),
        span("2026-08-20", "2026-08-25"),
        span("2026-08-21", "2026-08-22"),
      ]),
    ).toEqual([span("2026-08-01", "2026-08-08"), span("2026-08-20", "2026-08-25")]);
  });
});

describe("monthState", () => {
  it("is covered when one period contains the whole month", () => {
    expect(monthState([span("2026-07-15", "2026-09-02")], august, TODAY)).toBe("covered");
  });

  it("is partial when a period ends on the 5th", () => {
    expect(monthState([span("2026-06-01", "2026-08-05")], august, TODAY)).toBe("partial");
  });

  it("stays partial when two partials together fill the month", () => {
    const periods = [span("2026-08-01", "2026-08-15"), span("2026-08-16", "2026-08-31")];
    expect(monthState(periods, august, TODAY)).toBe("partial");
  });

  it("is a gap when an ended month falls between two periods", () => {
    const periods = [span("2026-07-01", "2026-07-31"), span("2026-09-01", "2026-09-30")];
    expect(monthState(periods, august, TODAY)).toBe("gap");
  });

  it("never calls the current month a gap", () => {
    expect(monthState([span("2026-09-01", "2026-09-30")], monthSpan("2026-10"), TODAY)).toBe("outside");
  });

  it("calls the current month partial when a statement reaches into it", () => {
    expect(monthState([span("2026-09-01", "2026-10-10")], monthSpan("2026-10"), TODAY)).toBe("partial");
  });

  it("waits for the month's last day to pass before calling it a gap", () => {
    const periods = [span("2026-09-01", "2026-09-30")];
    expect(monthState(periods, monthSpan("2026-10"), "2026-10-31")).toBe("outside");
    expect(monthState(periods, monthSpan("2026-10"), "2026-11-01")).toBe("gap");
  });

  it("is outside before the account's first period", () => {
    expect(monthState([span("2026-03-01", "2026-03-31")], monthSpan("2026-02"), TODAY)).toBe("outside");
  });
});

describe("buildYear", () => {
  it("orders accounts by name and puts January at index 0", () => {
    const board = buildYear(ACCOUNTS, [row("a", "2026-01-01", "2026-01-31")], 2026, TODAY);
    expect(board.months).toHaveLength(12);
    expect(board.months[0]).toBe("2026-01");
    expect(board.months[11]).toBe("2026-12");
    expect(board.accounts.map((account) => account.name)).toEqual(["ZZTEST Everyday", "ZZTEST Savings"]);
    expect(board.accounts[0].states[0]).toBe("covered");
    expect(board.accounts[0].digits).toBeNull();
    expect(board.accounts[1].states).toEqual(Array(12).fill("outside"));
  });

  it("lists a partial month with its clipped, merged days", () => {
    const imports = [row("a", "2026-06-01", "2026-08-03"), row("a", "2026-08-04", "2026-08-05")];
    expect(buildYear(ACCOUNTS, imports, 2026, TODAY).byMonth[7].partial).toEqual([
      { id: "a", name: "ZZTEST Everyday", count: 2, spans: [span("2026-08-01", "2026-08-05")] },
    ]);
  });

  it("counts two statements that each cover a month and draws one covered state", () => {
    const imports = [row("b", "2026-03-01", "2026-03-31"), row("b", "2026-03-01", "2026-03-31")];
    const board = buildYear(ACCOUNTS, imports, 2026, TODAY);
    expect(board.accounts[1].states[2]).toBe("covered");
    expect(board.byMonth[2].covered).toEqual([{ id: "b", name: "ZZTEST Savings", count: 2 }]);
  });

  it("ignores a period with a null end: it paints nothing and makes no later gap", () => {
    const board = buildYear(ACCOUNTS, [row("a", "2026-01-01", null)], 2026, TODAY);
    expect(board.accounts[0].states).toEqual(Array(12).fill("outside"));
    expect(board.byMonth.every((month) => month.missing.length === 0)).toBe(true);
  });

  it("lists missing accounts by id, so two accounts with one name both show", () => {
    const twins: AccountRef[] = [
      { id: "x", name: "ZZTEST Joint", digits: "····0003" },
      { id: "y", name: "ZZTEST Joint", digits: "····0004" },
    ];
    const imports = [row("x", "2026-01-01", "2026-01-31"), row("y", "2026-01-01", "2026-01-31")];
    const board = buildYear(twins, imports, 2026, TODAY);
    expect(board.accounts.map((account) => account.id)).toEqual(["x", "y"]);
    expect(board.byMonth[1].missing.map((line) => line.id)).toEqual(["x", "y"]);
  });

  it("draws a statement across New Year in both years", () => {
    const imports = [row("a", "2025-12-01", "2026-01-31")];
    expect(buildYear(ACCOUNTS, imports, 2025, TODAY).accounts[0].states[11]).toBe("covered");
    expect(buildYear(ACCOUNTS, imports, 2026, TODAY).accounts[0].states[0]).toBe("covered");
  });
});

describe("yearBounds", () => {
  it("opens on the latest statement's year and runs to the current year", () => {
    const imports = [row("a", "2024-12-01", "2025-01-31"), row("b", "2025-03-01", "2025-03-31"), row("a", null, null)];
    expect(yearBounds(imports, TODAY)).toEqual({ first: 2024, last: 2026, initial: 2025 });
  });

  it("falls back to the current year without any dated statement", () => {
    expect(yearBounds([row("a", null, null)], TODAY)).toEqual({ first: 2026, last: 2026, initial: 2026 });
  });
});

describe("missingSummary", () => {
  it("lists the newest month first, with every missing account", () => {
    const imports = [
      row("a", "2026-01-01", "2026-08-31"),
      row("b", "2026-01-01", "2026-03-31"),
      row("b", "2026-05-01", "2026-08-31"),
    ];
    expect(missingSummary(buildYear(ACCOUNTS, imports, 2026, TODAY))).toEqual([
      { month: "2026-09", names: ["ZZTEST Everyday", "ZZTEST Savings"] },
      { month: "2026-04", names: ["ZZTEST Savings"] },
    ]);
  });
});
