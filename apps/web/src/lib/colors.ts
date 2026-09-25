/** Colour follows the group, never its rank (spec 7.2). Slots 1-5 come from the API
 * (Overview.group_slots, by all-time spend), so a period filter never repaints a group. */

import type { Schemas } from "./api";

type Row = Schemas["BreakdownRow"];

export const OTHER_COLOR = "var(--chart-other)";

export function groupColor(level1: string | null | undefined, slots: Record<string, number>): string {
  const slot = level1 ? slots[level1] : undefined;
  return slot ? `var(--chart-${slot})` : OTHER_COLOR;
}

/** The one-hue ramp inside a group page, darkest = largest; the 6th step also paints "_other". */
export const rampColor = (index: number) => `var(--ramp-${Math.min(index, 5) + 1})`;

const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);

/** The Groups view shows the five coloured groups and folds the rest into one "Other" row
 * (spec 7.2). The API ranks its top five by the period's spend, so a group without a slot can
 * be among them: it is folded here, with the API's own "_other" row. */
export function foldBySlot(rows: Row[], slots: Record<string, number>): Row[] {
  const kept = rows.filter((row) => row.key !== "_other" && slots[row.key] !== undefined);
  const rest = rows.filter((row) => !kept.includes(row));
  if (rest.length === 0) return rows;
  const other: Row = {
    key: "_other",
    label: null,
    level1: null,
    category_slug: null,
    merchant_id: null,
    amount: sum(rest.map((row) => Number(row.amount))).toFixed(2),
    share: Math.round(sum(rest.map((row) => row.share)) * 10_000) / 10_000,
    previous: rest.every((row) => row.previous !== null) ? sum(rest.map((row) => Number(row.previous))).toFixed(2) : null,
    count: sum(rest.map((row) => row.count)),
    folded: sum(rest.map((row) => (row.key === "_other" ? (row.folded ?? 0) : 1))),
  };
  return [...kept, other];
}
