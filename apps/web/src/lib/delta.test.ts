import { describe, expect, it } from "vitest";

import { atSameDay, delta, periodHasData } from "./delta";

describe("delta", () => {
  it("reads spending that went down as good", () => {
    expect(delta(2184, 2374, "down", "percent")).toEqual({ kind: "change", direction: "down", tone: "good", text: "−8%" });
  });

  it("reads income, savings and the rate that went up as good", () => {
    expect(delta(3250, 3186, "up", "percent")).toMatchObject({ tone: "good", text: "+2%" });
    expect(delta(1066, 811, "up", "euro")).toMatchObject({ direction: "up", tone: "good", text: "+€255" });
    expect(delta(0.328, 0.258, "up", "points")).toMatchObject({ tone: "good", text: "+7 pts" });
  });

  it("reads more spending as bad", () => {
    expect(delta(306.4, 273.6, "down", "percent")).toMatchObject({ direction: "up", tone: "bad", text: "+12%" });
  });

  it("reads income, savings and the rate that went down as bad, with a minus sign", () => {
    expect(delta(3000, 3250, "up", "percent")).toEqual({ kind: "change", direction: "down", tone: "bad", text: "−8%" });
    expect(delta(811, 1066, "up", "euro")).toEqual({ kind: "change", direction: "down", tone: "bad", text: "−€255" });
    expect(delta(0.258, 0.328, "up", "points")).toEqual({ kind: "change", direction: "down", tone: "bad", text: "−7 pts" });
  });

  it("hides the delta without previous data and says new after a zero", () => {
    expect(delta(100, null, "down", "percent")).toEqual({ kind: "hidden" });
    expect(delta(100, undefined, "down", "percent")).toEqual({ kind: "hidden" });
    expect(delta(null, 0.2, "up", "points")).toEqual({ kind: "hidden" });
    expect(delta(51, 0, "down", "percent")).toEqual({ kind: "new" });
    expect(delta(0, 0, "down", "percent")).toEqual({ kind: "change", direction: "flat", tone: "neutral", text: "0%" });
  });

  it("never reads a fall to an amount that is not zero as −100%", () => {
    expect(delta(2, 1000, "down", "percent")).toEqual({ kind: "change", direction: "down", tone: "good", text: "−99%" });
    expect(delta(0, 1000, "down", "percent")).toMatchObject({ text: "−100%" });
  });

  it("keeps a real −100% when either amount is not positive", () => {
    // Twice as negative as a negative month (refunds only), and a fall just past zero.
    expect(delta(-60, -30, "down", "percent")).toMatchObject({ direction: "down", text: "−100%" });
    expect(delta(-0.3, 100, "down", "percent")).toMatchObject({ direction: "down", text: "−100%" });
  });

  it("compares with a negative month (refunds only) by its size", () => {
    expect(delta(120, -30, "down", "percent")).toMatchObject({ direction: "up", tone: "bad", text: "+500%" });
  });
});

describe("atSameDay", () => {
  const points = (...totals: string[]) => totals.map((total) => ({ total }));

  it("reads the previous period at the current period's latest day", () => {
    expect(atSameDay({ current: points("10", "30"), previous: points("5", "20", "60") })).toEqual({ current: 30, previous: 20 });
  });

  it("uses the end of a shorter previous period, and nothing without one", () => {
    expect(atSameDay({ current: points("1", "2", "3"), previous: points("7", "9") })).toEqual({ current: 3, previous: 9 });
    expect(atSameDay({ current: points("4"), previous: null })).toEqual({ current: 4, previous: null });
  });

  it("reads no data, never 0, when the current series is empty", () => {
    // The API sends [] when the period starts after the latest imported day, or there is no data.
    expect(atSameDay({ current: [], previous: points("5", "20") })).toEqual({ current: null, previous: null });
  });
});

describe("periodHasData", () => {
  const months = [
    { month: "2026-06", has_data: true },
    { month: "2026-07", has_data: false },
    { month: "2026-08", has_data: false },
  ];

  it("reads only the months of the period (Decision G: no data, never 0)", () => {
    expect(periodHasData(months, { start: "2026-08-01", end: "2026-08-31" })).toBe(false);
    expect(periodHasData(months, { start: "2026-07-10", end: "2026-08-19" })).toBe(false);
    expect(periodHasData(months, { start: "2026-06-01", end: "2026-08-31" })).toBe(true);
  });

  it("trusts the API's numbers for a range that starts before the 12-month series", () => {
    expect(periodHasData(months, { start: "2025-01-01", end: "2026-08-31" })).toBe(true);
    expect(periodHasData([], { start: "2026-08-01", end: "2026-08-31" })).toBe(true);
  });
});
