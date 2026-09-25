/** Breakdown rows as the tables and donuts show them: named, linked one level deeper, coloured
 * by group on the overview (spec 7.2), and compared with the previous period. */

import type { Schemas } from "./api";
import { groupColor } from "./colors";
import { delta, type Delta, type Good } from "./delta";
import { rowHint, rowName, type Dimension } from "./labels";
import { withFilters, type Filters } from "./params";

type Row = Schemas["BreakdownRow"];

export type BreakdownItem = {
  key: string;
  name: string;
  hint: string;
  href: string | null;
  color?: string;
  share: number;
  amount: string;
  delta: Delta;
};

export type BreakdownContext = {
  categories: Schemas["CategoryOut"][];
  slots: Record<string, number> | null; // null: no group colours (the detail pages use the ramp)
  filters: Filters;
  good: Good;
  type: "expense" | "income";
};

function hrefOf(row: Row, dimension: Dimension, { filters, type }: BreakdownContext): string | null {
  if (row.key === "_other") return null;
  if (dimension === "group") return withFilters(`/spending/${row.key}`, filters);
  if (dimension === "category") {
    return withFilters(type === "income" ? `/income/${row.key}` : `/spending/${row.level1 ?? "uncategorized"}/${row.key}`, filters);
  }
  if (!row.merchant_id) return null;
  return withFilters(`/merchants/${row.merchant_id}`, filters, { type: type === "income" ? "income" : undefined });
}

export function breakdownItems(rows: Row[], dimension: Dimension, context: BreakdownContext): BreakdownItem[] {
  return rows.map((row) => ({
    key: row.key,
    name: rowName(row, dimension),
    hint: rowHint(row, dimension, context.categories),
    href: hrefOf(row, dimension, context),
    color: context.slots
      ? groupColor(dimension === "group" && row.key !== "_other" ? row.key : row.level1, context.slots)
      : undefined,
    share: row.share,
    amount: row.amount,
    delta: delta(Number(row.amount), row.previous === null ? null : Number(row.previous), context.good, "percent"),
  }));
}
