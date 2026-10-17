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
const acmeMerge = card("merge:acme", "merge", "acme", "foods");
const foods = card("m:foods", "merchant", "foods");
const foodsMerge = card("merge:foods", "merge", "foods");
const other = card("m:other", "merchant", "other");
const otherMerge = card("merge:other", "merge", "other");
// Suggests acme: a merge of acme clears it on the server.
const shopMerge = card("merge:shop", "merge", "shop", "acme");
const items = [acme, acmeMerge, foods, foodsMerge, other, otherMerge, shopMerge];
const keys = (list: Item[]) => list.map((item) => item.key);

describe("settledByConfirm", () => {
  it("settles the merchant's own duplicate suggestion", () => {
    expect(keys(settledByConfirm(items, "acme", null))).toEqual(["merge:acme"]);
  });

  it("with a merge, settles the survivor's category card and every duplicate card the merge touches", () => {
    expect(keys(settledByConfirm(items, "acme", "foods"))).toEqual(["m:foods", "merge:acme", "merge:foods", "merge:shop"]);
  });

  it("settles nothing when the merchant has no other card", () => {
    expect(settledByConfirm([acme, other], "acme", null)).toEqual([]);
  });
});

describe("settledByMerge", () => {
  it("settles the source's category card and the other duplicate cards the merge touches", () => {
    expect(keys(settledByMerge(items, acmeMerge))).toEqual(["m:acme", "merge:foods", "merge:shop"]);
  });
});
