import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { groupByDay } from "./transactions";

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
