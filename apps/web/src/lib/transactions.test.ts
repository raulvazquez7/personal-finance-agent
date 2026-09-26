import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { applyChange, groupByDay } from "./transactions";

type Tx = Schemas["Transaction"];

const tx = (id: string, day: string, amount: string, fields: Partial<Tx> = {}): Tx => ({
  id,
  booked_at: day,
  account_id: "a",
  account_name: "ZZTEST ACCOUNT",
  amount,
  description_raw: "ZZTEST",
  bank_merchant_text: null,
  merchant_id: null,
  merchant_name: null,
  tx_type: "expense",
  category_slug: null,
  level1: null,
  category_source: "none",
  is_subscription: false,
  needs_review: false,
  note: null,
  transfer_pair_id: null,
  ...fields,
});

describe("groupByDay", () => {
  it("groups rows by day with the day's net", () => {
    const days = groupByDay([tx("1", "2026-08-26", "-42.10"), tx("2", "2026-08-26", "-16.30"), tx("3", "2026-08-25", "51.00")]);
    expect(days.map((d) => [d.day, d.net.toFixed(2), d.items.length])).toEqual([
      ["2026-08-26", "-58.40", 2],
      ["2026-08-25", "51.00", 1],
    ]);
  });

  it("keeps one header for a day split across two pages", () => {
    const firstPage = [tx("1", "2026-08-26", "-10.00")];
    const secondPage = [tx("2", "2026-08-26", "-5.00"), tx("3", "2026-08-24", "-1.00")];
    const days = groupByDay([...firstPage, ...secondPage]);
    expect(days.map((d) => [d.day, d.net, d.items.length])).toEqual([
      ["2026-08-26", -15, 2],
      ["2026-08-24", -1, 1],
    ]);
  });
});

const categories: Schemas["CategoryOut"][] = [
  { slug: "fashion", tx_type: "expense", level1: "shopping" },
  { slug: "salary", tx_type: "income", level1: "income" },
];

describe("applyChange", () => {
  it("labels the edited row as the user's and keeps its note", () => {
    const [row] = applyChange(
      [tx("1", "2026-08-26", "-51.00", { merchant_id: "m", merchant_name: "ZZTEST ACME" })],
      { id: "1", categorySlug: "fashion", isSubscription: true, merchant: null, note: "AirPods case", defaultFor: null },
      categories,
    );
    expect(row).toMatchObject({
      category_slug: "fashion",
      level1: "shopping",
      tx_type: "expense",
      category_source: "user",
      is_subscription: true,
      needs_review: false,
      note: "AirPods case",
      merchant_id: "m",
    });
  });

  it("gives the merchant's other rows its new default, except the ones the user or a rule labelled", () => {
    const rows = [
      tx("1", "2026-08-26", "-1.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "-2.00", { merchant_id: "m", category_source: "jev" }),
      tx("3", "2026-08-26", "-3.00", { merchant_id: "m", category_source: "user", category_slug: "salary" }),
      tx("4", "2026-08-26", "-4.00", { merchant_id: "m", category_source: "rule" }),
      tx("5", "2026-08-26", "-5.00", { merchant_id: "x", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "fashion", isSubscription: false, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_source, row.category_slug])).toEqual([
      ["1", "user", "fashion"],
      ["2", "merchant", "fashion"],
      ["3", "user", "salary"],
      ["4", "rule", null],
      ["5", "jev", null],
    ]);
  });

  it("leaves the merchant's money out alone when its new default is income", () => {
    const rows = [
      tx("1", "2026-08-26", "100.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "100.00", { merchant_id: "m", category_source: "jev" }),
      tx("3", "2026-08-26", "-10.00", { merchant_id: "m", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "salary", isSubscription: false, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_source, row.category_slug])).toEqual([
      ["1", "user", "salary"],
      ["2", "merchant", "salary"],
      ["3", "jev", null],
    ]);
  });

  it("gives the merchant's money out its subscription answer, and its money in never", () => {
    const rows = [
      tx("1", "2026-08-26", "-1.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "-2.00", { merchant_id: "m", category_source: "jev" }),
      tx("3", "2026-08-26", "80.00", { merchant_id: "m", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "fashion", isSubscription: true, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_slug, row.is_subscription])).toEqual([
      ["1", "fashion", true],
      ["2", "fashion", true],
      ["3", "fashion", false],
    ]);
  });

  it("keeps every row's own subscription mark when a default set from money in has no answer", () => {
    const rows = [
      tx("1", "2026-08-26", "80.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "-2.00", { merchant_id: "m", category_source: "jev", is_subscription: true }),
      tx("3", "2026-08-26", "-3.00", { merchant_id: "m", category_source: "merchant" }),
      tx("4", "2026-08-26", "100.00", { merchant_id: "m", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "fashion", isSubscription: null, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_source, row.category_slug, row.is_subscription])).toEqual([
      ["1", "user", "fashion", false],
      ["2", "merchant", "fashion", true],
      ["3", "merchant", "fashion", false],
      ["4", "merchant", "fashion", false],
    ]);
  });

  it("never makes money in a subscription, and a note-only change keeps the label", () => {
    const [refund] = applyChange(
      [tx("1", "2026-08-26", "80.00")],
      { id: "1", categorySlug: "fashion", isSubscription: true, merchant: null, note: null, defaultFor: null },
      categories,
    );
    expect(refund).toMatchObject({ tx_type: "expense", is_subscription: false });
    const [noted] = applyChange(
      [tx("1", "2026-08-26", "-5.00", { category_slug: "fashion", level1: "shopping", category_source: "jev" })],
      { id: "1", categorySlug: null, isSubscription: false, merchant: null, note: "gift", defaultFor: null },
      categories,
    );
    expect(noted).toMatchObject({ category_slug: "fashion", category_source: "jev", note: "gift" });
  });

  it("moves the row to a newly named merchant without inventing its id", () => {
    const [row] = applyChange(
      [tx("1", "2026-08-26", "-9.00", { merchant_id: "old" })],
      { id: "1", categorySlug: "fashion", isSubscription: false, merchant: { id: null, name: "ZZTEST NEW" }, note: null, defaultFor: null },
      categories,
    );
    expect(row).toMatchObject({ merchant_id: null, merchant_name: "ZZTEST NEW" });
  });
});
