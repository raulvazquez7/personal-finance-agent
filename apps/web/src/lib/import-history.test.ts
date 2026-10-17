import { describe, expect, it } from "vitest";

import { groupByEndMonth } from "./import-history";

const record = (id: string, period_end: string | null) => ({ id, period_end });

describe("groupByEndMonth", () => {
  it("groups by the month a statement ends, keeping the API order", () => {
    // "2" is a statement from 1 June to 5 August: it belongs to August.
    const rows = [record("1", "2026-08-31"), record("2", "2026-08-05"), record("3", "2026-07-31")];
    expect(groupByEndMonth(rows)).toEqual([
      { month: "2026-08", rows: [rows[0], rows[1]] },
      { month: "2026-07", rows: [rows[2]] },
    ]);
  });

  it("puts statements without a period in a last group", () => {
    const rows = [record("1", "2026-08-31"), record("2", null)];
    expect(groupByEndMonth(rows)).toEqual([
      { month: "2026-08", rows: [rows[0]] },
      { month: null, rows: [rows[1]] },
    ]);
  });

  it("returns nothing for no imports", () => {
    expect(groupByEndMonth([])).toEqual([]);
  });
});
