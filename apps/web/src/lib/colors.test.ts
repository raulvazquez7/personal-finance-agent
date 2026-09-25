import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { foldBySlot, groupColor, rampColor } from "./colors";

type Row = Schemas["BreakdownRow"];

const slots = { home: 1, shopping: 2, leisure: 3, transport: 4, credit_card: 5 };
const row = (key: string, amount: string, share: number, previous: string | null, folded = 0): Row => ({
  key,
  label: null,
  level1: key === "_other" ? null : key,
  category_slug: null,
  merchant_id: null,
  amount,
  share,
  previous,
  count: 1,
  folded,
});

describe("colours", () => {
  it("paints a group by its slot, never by its rank", () => {
    expect(groupColor("shopping", slots)).toBe("var(--chart-2)");
    expect(groupColor("health", slots)).toBe("var(--chart-other)");
    expect(groupColor(null, slots)).toBe("var(--chart-other)");
  });

  it("steps the ramp and keeps its last step for the rest", () => {
    expect([0, 1, 5, 9].map(rampColor)).toEqual(["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-6)", "var(--ramp-6)"]);
  });

  it("folds the groups without a colour into Other", () => {
    const folded = foldBySlot(
      [
        row("home", "830.00", 0.38, "800.00"),
        row("health", "100.00", 0.05, "90.00"),
        row("shopping", "481.20", 0.22, "500.00"),
        row("_other", "94.80", 0.04, "100.00", 3),
      ],
      slots,
    );
    expect(folded.map((r) => r.key)).toEqual(["home", "shopping", "_other"]);
    expect(folded[2]).toMatchObject({ amount: "194.80", share: 0.09, previous: "190.00", folded: 4, count: 2 });
  });

  it("leaves the rows alone when every group has a colour", () => {
    const rows = [row("home", "10.00", 1, null)];
    expect(foldBySlot(rows, slots)).toBe(rows);
  });
});
