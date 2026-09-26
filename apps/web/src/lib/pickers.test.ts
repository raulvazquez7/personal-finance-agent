import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { directionOf, filterGroups, fitsDirection, pickerGroups } from "./pickers";

const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping" },
  { slug: "fashion", tx_type: "expense", level1: "shopping" },
  { slug: "rent", tx_type: "expense", level1: "home" },
  { slug: "salary", tx_type: "income", level1: "income" },
  { slug: "refunds", tx_type: "income", level1: "income" },
  { slug: "own_accounts", tx_type: "transfer", level1: "transfer" },
];
const slugs = (groups: { items: { slug: string }[] }[]) => groups.map((group) => group.items.map((item) => item.slug));

describe("pickerGroups", () => {
  it("offers expense and transfer categories for money out", () => {
    const groups = pickerGroups(categories, "out");
    expect(groups.map((group) => group.label)).toEqual(["Shopping", "Home", "Transfer"]);
    expect(slugs(groups)).toEqual([["groceries", "fashion"], ["rent"], ["own_accounts"]]);
  });

  it("offers income first, then refunds of a purchase, then transfers for money in", () => {
    const groups = pickerGroups(categories, "in");
    expect(groups.map((group) => group.label)).toEqual(["Income", "Refund of a purchase", "Transfer"]);
    expect(slugs(groups)).toEqual([["salary", "refunds"], ["groceries", "fashion", "rent"], ["own_accounts"]]);
  });

  it("keeps only the suggestions that fit the direction", () => {
    const [suggested] = pickerGroups(categories, "out", ["salary", "fashion"]);
    expect(suggested.label).toBe("Suggested");
    expect(suggested.items.map((item) => item.slug)).toEqual(["fashion"]);
    expect(pickerGroups(categories, "out", ["salary"])[0].label).toBe("Shopping");
  });

  it("keeps an expense score as a refund suggestion for money in", () => {
    const [suggested] = pickerGroups(categories, "in", ["fashion", "unknown", "salary"]);
    expect(suggested.label).toBe("Suggested");
    expect(suggested.items.map((item) => item.slug)).toEqual(["fashion", "salary"]);
  });

  it("reads a merchant with purchases and refunds as money out", () => {
    expect(directionOf(["15.00", "-20.00"])).toBe("out");
    expect(directionOf(["2000.00"])).toBe("in");
  });
});

describe("fitsDirection", () => {
  it("tells whether a category fits the direction (Decision H)", () => {
    expect(fitsDirection("salary", categories, "out")).toBe(false);
    expect(fitsDirection("fashion", categories, "out")).toBe(true);
    // A refund keeps its purchase's category, so money in takes any category.
    expect(fitsDirection("fashion", categories, "in")).toBe(true);
    expect(fitsDirection("unknown", categories, "in")).toBe(false);
  });
});

describe("filterGroups", () => {
  it("follows the type filter and starts each group with the whole group", () => {
    expect(filterGroups(categories, "income")).toEqual([
      {
        value: "income",
        label: "Income",
        items: [
          { kind: "group", value: "income", label: "All of Income" },
          { kind: "category", value: "salary", label: "Salary" },
          { kind: "category", value: "refunds", label: "Refunds" },
        ],
      },
    ]);
    expect(filterGroups(categories).map((group) => group.value)).toEqual(["shopping", "home", "income", "transfer"]);
  });
});
