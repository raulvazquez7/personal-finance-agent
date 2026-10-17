import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { reviewOrder } from "./review-order";

type Item = Schemas["ReviewItem"];

const suggestion = { category_slug: null, level1: null, confidence: null, is_subscription: false, top: [] };

function card(key: string, total: string, days: string[]): Item {
  return {
    key,
    kind: "merchant",
    merchant: null,
    transactions: days.map((booked_at, i) => ({
      id: `${key}-${i}`,
      booked_at,
      amount: total,
      description_raw: "PAGO | ACME",
      account_name: "bank ····0001",
    })),
    count: days.length,
    total,
    suggestion,
    merge: null,
  };
}

function merge(key: string, confidence: number): Item {
  return {
    ...card(key, "0", []),
    kind: "merge",
    merge: { merchant_id: `${key}-target`, name: "ACME FOODS", confidence },
  };
}

const small = card("small", "-5", ["2026-07-20"]);
const large = card("large", "-50", ["2026-06-01", "2026-06-03"]);
const refund = card("refund", "20", ["2026-07-01"]);
const sure = merge("sure", 0.9);
const unsure = merge("unsure", 0.4);
const items = [unsure, small, sure, refund, large];
const keys = (list: Item[]) => list.map((item) => item.key);

describe("reviewOrder", () => {
  it("sorts by absolute amount, with merge cards last by confidence", () => {
    expect(keys(reviewOrder(items, "all", "amount", []))).toEqual(["large", "refund", "small", "sure", "unsure"]);
  });

  it("sorts by the latest transaction on the card, with merge cards last", () => {
    expect(keys(reviewOrder(items, "all", "date", []))).toEqual(["small", "refund", "large", "sure", "unsure"]);
  });

  it("filters category cards apart from duplicate suggestions", () => {
    expect(keys(reviewOrder(items, "categories", "amount", []))).toEqual(["large", "refund", "small"]);
    expect(keys(reviewOrder(items, "duplicates", "amount", []))).toEqual(["sure", "unsure"]);
  });

  it("moves skipped cards to the end, in the order they were skipped", () => {
    expect(keys(reviewOrder(items, "all", "amount", ["refund", "large"]))).toEqual([
      "small",
      "sure",
      "unsure",
      "refund",
      "large",
    ]);
  });
});
