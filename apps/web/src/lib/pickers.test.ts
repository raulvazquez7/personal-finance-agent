import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import type { TxType } from "./params";
import { directionOf, filterGroups, fitsDirection, pickerGroups, selectedFilter } from "./pickers";

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

  it("offers income first, then refunds of a purchase per expense group, then transfers for money in", () => {
    const groups = pickerGroups(categories, "in");
    expect(groups.map((group) => group.label)).toEqual([
      "Income",
      "Refund of a purchase · Shopping",
      "Refund of a purchase · Home",
      "Transfer",
    ]);
    expect(slugs(groups)).toEqual([["salary", "refunds"], ["groceries", "fashion"], ["rent"], ["own_accounts"]]);
    // The picker keys its groups by value.
    expect(new Set(groups.map((group) => group.value)).size).toBe(groups.length);
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
          { kind: "category", value: "uncategorized", label: "Uncategorized" },
        ],
      },
    ]);
    expect(filterGroups(categories).map((group) => group.value)).toEqual([
      "shopping",
      "home",
      "income",
      "transfer",
      "uncategorized",
    ]);
  });

  it("offers the rows without a category the way the detail pages link to them (knownGroup, knownCategory)", () => {
    const group = {
      value: "uncategorized",
      label: "Uncategorized",
      items: [{ kind: "group", value: "uncategorized", label: "Uncategorized" }],
    };
    const option = { kind: "category", value: "uncategorized", label: "Uncategorized" };
    const incomeTail = (txType?: TxType) => filterGroups(categories, txType).find((g) => g.value === "income")?.items.at(-1);
    // Money out: a group of its own, for expenses and for all types.
    expect(filterGroups(categories, "expense").at(-1)).toEqual(group);
    expect(filterGroups(categories).at(-1)).toEqual(group);
    // Money in: a category of Income, for income only.
    expect(incomeTail("income")).toEqual(option);
    // All types list it once: the group matches the rows without a category in both directions.
    expect(incomeTail()).toEqual({ kind: "category", value: "refunds", label: "Refunds" });
    const labels = filterGroups(categories).flatMap((g) => g.items.map((item) => item.label));
    expect(labels.filter((text) => text === "Uncategorized")).toHaveLength(1);
    // Transfers have neither.
    expect(filterGroups(categories, "transfer").map((g) => g.value)).toEqual(["transfer"]);
    expect(filterGroups(categories, "transfer")[0].items.map((item) => item.value)).toEqual(["transfer", "own_accounts"]);
  });
});

describe("selectedFilter", () => {
  const expense = filterGroups(categories, "expense");

  it("selects the category the URL names, else its group", () => {
    expect(selectedFilter(expense, "shopping", "fashion")).toEqual({ kind: "category", value: "fashion", label: "Fashion" });
    expect(selectedFilter(expense, "shopping")).toEqual({ kind: "group", value: "shopping", label: "All of Shopping" });
    expect(selectedFilter(expense)).toBeNull();
  });

  it("falls back to the group only for the rows without a category", () => {
    // The uncategorized group's page links with level1 and category both "uncategorized".
    expect(selectedFilter(expense, "uncategorized", "uncategorized")).toEqual({
      kind: "group",
      value: "uncategorized",
      label: "Uncategorized",
    });
    expect(selectedFilter(filterGroups(categories), "uncategorized", "uncategorized")?.kind).toBe("group");
    // A hand-edited category never shows as "All of <group>", which would not be the filter applied.
    expect(selectedFilter(expense, "shopping", "zztest_unknown")).toBeNull();
  });
});
