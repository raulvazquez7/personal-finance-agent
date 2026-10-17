import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { settledByConfirm, settledByMerge } from "./review-settled";

type Item = Schemas["ReviewItem"];

const suggestion = { category_slug: null, level1: null, confidence: null, is_subscription: false, top: [] };

function card(key: string, kind: Item["kind"], merchantId: string | null, candidate = "elsewhere"): Item {
  return {
    key,
    kind,
    merchant: merchantId ? { id: merchantId, name: "ACME" } : null,
    transactions: [],
    count: 0,
    total: "0",
    suggestion,
    merge: kind === "merge" ? { merchant_id: candidate, name: "ACME FOODS", confidence: 0.6 } : null,
  };
}

const acme = card("m:acme", "merchant", "acme");
// A single row of acme: money out under an income default stands alone.
const acmeRow = card("t:acme-row", "transaction", "acme");
const acmeMerge = card("merge:acme", "merge", "acme", "foods");
const foods = card("m:foods", "merchant", "foods");
const foodsRow = card("t:foods-row", "transaction", "foods");
const foodsMerge = card("merge:foods", "merge", "foods");
const other = card("m:other", "merchant", "other");
const otherMerge = card("merge:other", "merge", "other");
// Suggests acme: a merge of acme clears it on the server.
const shopMerge = card("merge:shop", "merge", "shop", "acme");
const items = [acme, acmeRow, acmeMerge, foods, foodsRow, foodsMerge, other, otherMerge, shopMerge];
const keys = (list: Item[]) => list.map((item) => item.key);

describe("settledByConfirm", () => {
  it("settles no duplicate card: the category and the duplicate are separate questions", () => {
    expect(settledByConfirm(items, acme, null)).toEqual([]);
  });

  it("with a merge, settles the survivor's category cards and every card of the source", () => {
    expect(keys(settledByConfirm(items, acme, "foods"))).toEqual([
      "m:foods",
      "t:foods-row",
      "t:acme-row",
      "merge:acme",
      "merge:shop",
    ]);
  });
});

describe("settledByMerge", () => {
  it("settles every other card of the source and the duplicate cards that suggest it", () => {
    expect(keys(settledByMerge(items, acmeMerge))).toEqual(["m:acme", "t:acme-row", "merge:shop"]);
  });

  it("keeps the survivor's own duplicate card", () => {
    expect(keys(settledByMerge(items, acmeMerge))).not.toContain("merge:foods");
  });
});
