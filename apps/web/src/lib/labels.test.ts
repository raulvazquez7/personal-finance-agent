import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { SOURCES } from "./params";
import {
  DIGITS_SEPARATOR,
  accountDigits,
  accountsLabel,
  categoryName,
  groupHint,
  groupName,
  knownCategory,
  knownGroup,
  label,
  plural,
  rowHint,
  rowName,
  sourceLabel,
} from "./labels";

type Row = Schemas["BreakdownRow"];

const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping", name: "Groceries", group_name: "Shopping" },
  { slug: "fashion", tx_type: "expense", level1: "shopping", name: "Fashion", group_name: "Shopping" },
  { slug: "electronics", tx_type: "expense", level1: "shopping", name: "Electronics", group_name: "Shopping" },
  { slug: "home_goods", tx_type: "expense", level1: "shopping", name: "Home goods", group_name: "Shopping" },
  { slug: "credit_card_spending", tx_type: "expense", level1: "credit_card", name: "Credit card bill", group_name: "Credit card" },
  { slug: "salary", tx_type: "income", level1: "income", name: "Salary", group_name: "Income" },
  // Taxonomy order is parking then fuel. A group hint that ignores top_categories reads that order.
  { slug: "parking_tolls", tx_type: "expense", level1: "transport", name: "Parking & tolls", group_name: "Transport" },
  { slug: "fuel", tx_type: "expense", level1: "transport", name: "Fuel", group_name: "Transport" },
];
const row = (fields: Partial<Row> & { key: string }): Row => ({
  label: null,
  level1: null,
  category_slug: null,
  merchant_id: null,
  amount: "0.00",
  share: 0,
  previous: null,
  count: 1,
  folded: 0,
  rows: [],
  category_count: 1,
  top_categories: [],
  ...fields,
});

describe("labels", () => {
  it("reads slugs as words", () => {
    expect(label("restaurants_bars")).toBe("Restaurants bars");
    expect(label(null)).toBe("Uncategorized");
    expect(plural(1, "transaction", "transactions")).toBe("1 transaction");
    expect(plural(31, "transaction", "transactions")).toBe("31 transactions");
  });

  it("shows the stored names, and the readable slug when a name is missing", () => {
    const software = { slug: "software_ai", tx_type: "expense", level1: "technology", name: "Software & AI", group_name: "Technology" };
    expect(categoryName("software_ai", [...categories, software])).toBe("Software & AI");
    expect(categoryName("software_ai", categories)).toBe("Software ai");
    expect(groupName("technology", [...categories, software])).toBe("Technology");
    expect(groupName("uncategorized", categories)).toBe("Uncategorized");
  });

  it("describes a group by its first categories", () => {
    expect(groupHint("shopping", categories)).toBe("Groceries, Fashion, Electronics…");
    expect(groupHint("credit_card", categories)).toBe("Not itemized: card statements are not imported");
    // Decision I: uncategorized rows never reach /review, so the hint does not send the user there.
    expect(groupHint("uncategorized", categories)).toBe("Not categorized yet");
    expect(groupHint("unknown", categories)).toBe("");
  });

  it("describes a group by the categories it spent on, in that order", () => {
    expect(rowHint(row({ key: "transport", top_categories: ["fuel", "parking_tolls"] }), "group", categories)).toBe(
      "Fuel, Parking & tolls",
    );
    // An empty list stays the taxonomy line (groupHint), not a blank.
    expect(rowHint(row({ key: "shopping" }), "group", categories)).toBe("Groceries, Fashion, Electronics…");
  });

  it("names rows, including the folded ones and merchants without a merchant", () => {
    expect(rowName(row({ key: "_other", folded: 12 }), "merchant", categories)).toBe("Other 12 merchants");
    // The folded row names its dimension, so it never reads like the real expense group "other".
    expect(rowName(row({ key: "_other", folded: 3 }), "group", categories)).toBe("Other groups");
    expect(rowName(row({ key: "_other", folded: 4 }), "category", categories)).toBe("Other categories");
    expect(rowName(row({ key: "other", level1: "other" }), "group", categories)).toBe("Other");
    expect(rowName(row({ key: "transport" }), "group", categories)).toBe("Transport");
    expect(rowName(row({ key: "parking_tolls", level1: "transport" }), "category", categories)).toBe("Parking & tolls");
    // Rows without a merchant never read like a merchant named after their category.
    const noMerchant = row({ key: "category:credit_card_spending", category_slug: "credit_card_spending", count: 3 });
    expect(rowName(noMerchant, "merchant", categories)).toBe("No merchant");
    expect(rowHint(noMerchant, "merchant", categories)).toBe("Credit card bill · 3 transactions");
    expect(rowHint(row({ key: "_other", folded: 3 }), "group", categories)).toBe("3 groups");
    expect(rowHint(row({ key: "fashion", level1: "shopping" }), "category", categories)).toBe("Shopping");
    expect(rowHint(row({ key: "m", category_slug: "groceries", count: 12 }), "merchant", categories)).toBe(
      "Groceries · 12 transactions",
    );
    expect(rowHint(row({ key: "m", category_slug: "groceries", category_count: 2, count: 4 }), "merchant", categories)).toBe(
      "2 categories · 4 transactions",
    );
  });

  it("labels sources and account selections", () => {
    expect(sourceLabel("jev")).toBe("AI (jev)");
    expect(sourceLabel("none")).toBe("Pending");
    // The explorer's "Categorized by" filter lists every source by its name.
    expect(SOURCES.map(sourceLabel)).toEqual(["Rule", "Merchant", "AI (jev)", "You", "Pending"]);
    const accounts = [{ id: "a", name: "Main" }, { id: "b", name: "Savings" }];
    expect(accountsLabel([], accounts)).toBe("All accounts");
    expect(accountsLabel(["b"], accounts)).toBe("Savings");
    expect(accountsLabel(["a", "b"], accounts)).toBe("2 accounts");
    // An account id the list does not know (renamed away, or a stale link) still reads as one account.
    expect(accountsLabel(["zztest-unknown"], accounts)).toBe("1 account");
    // The importer's default name already ends with the digits; a renamed account shows them again.
    expect(accountDigits({ name: "zztest ····1234", iban_last4: "1234" })).toBeNull();
    // One way to write the digits: the importer's four dots (Settings uses the same separator).
    expect(DIGITS_SEPARATOR).toBe("····");
    expect(accountDigits({ name: "ZZTEST joint", iban_last4: "1234" })).toBe("····1234");
  });

  it("knows which groups and categories exist", () => {
    expect(knownGroup("shopping", categories)).toBe(true);
    expect(knownGroup("uncategorized", categories)).toBe(true);
    expect(knownGroup("income", categories)).toBe(false);
    expect(knownCategory("fashion", categories, { type: "expense", level1: "shopping" })).toBe(true);
    expect(knownCategory("fashion", categories, { type: "expense", level1: "home" })).toBe(false);
    expect(knownCategory("uncategorized", categories, { type: "expense", level1: "uncategorized" })).toBe(true);
    // Uncategorized money in counts as income: /income lists it under the key "uncategorized".
    expect(knownCategory("uncategorized", categories, { type: "income" })).toBe(true);
    expect(knownCategory("salary", categories, { type: "income" })).toBe(true);
  });
});
