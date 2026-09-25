import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { breakdownItems } from "./breakdown";

type Row = Schemas["BreakdownRow"];

const M = "33333333-3333-4333-8333-333333333333";
const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping" },
  { slug: "salary", tx_type: "income", level1: "income" },
];
const august = { period: "month" as const, month: "2026-08", accounts: [] };
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
  ...fields,
});

describe("breakdownItems", () => {
  it("links a category one level deeper and paints it with its group", () => {
    const [groceries, other] = breakdownItems(
      [
        row({ key: "groceries", level1: "shopping", category_slug: "groceries", amount: "268.40", share: 0.56, previous: "280.00" }),
        row({ key: "_other", amount: "10.00", previous: "12.00", folded: 2 }),
      ],
      "category",
      { categories, slots: { shopping: 2 }, filters: august, good: "down", type: "expense" },
    );
    expect(groceries).toMatchObject({
      name: "Groceries",
      hint: "Shopping",
      href: "/spending/shopping/groceries?month=2026-08",
      color: "var(--chart-2)",
      share: 0.56,
      amount: "268.40",
    });
    expect(groceries.delta).toMatchObject({ tone: "good", text: "−4%" });
    expect(other).toMatchObject({ name: "Other", hint: "2 categories", href: null, color: "var(--chart-other)" });
  });

  it("opens a merchant with its type and leaves a row without a merchant unlinked", () => {
    const [employer, card] = breakdownItems(
      [
        row({ key: M, label: "ZZTEST EMPLOYER", merchant_id: M, category_slug: "salary", level1: "income", count: 2 }),
        row({ key: "category:credit_card_spending", category_slug: "credit_card_spending", level1: "credit_card" }),
      ],
      "merchant",
      { categories, slots: null, filters: august, good: "up", type: "income" },
    );
    expect(employer).toMatchObject({
      name: "ZZTEST EMPLOYER",
      hint: "Salary · 2 transactions",
      href: `/merchants/${M}?month=2026-08&type=income`,
    });
    expect(employer.color).toBeUndefined();
    expect(card).toMatchObject({ name: "Credit card spending", href: null });
  });

  it("links a group to its page and an income category to the income pages", () => {
    const [home] = breakdownItems([row({ key: "home", level1: "home" })], "group", {
      categories,
      slots: { home: 1 },
      filters: { period: "ytd", accounts: [] },
      good: "down",
      type: "expense",
    });
    expect(home).toMatchObject({ href: "/spending/home?period=ytd", color: "var(--chart-1)" });
    const [salary] = breakdownItems([row({ key: "salary", level1: "income" })], "category", {
      categories,
      slots: null,
      filters: august,
      good: "up",
      type: "income",
    });
    expect(salary.href).toBe("/income/salary?month=2026-08");
  });
});
