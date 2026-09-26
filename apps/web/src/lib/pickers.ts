/** Category pickers follow the money's direction (spec 7.3). A refund is money in with the
 * purchase's expense category (spec 2.2), so money in must still offer the expense categories. */

import type { Schemas } from "./api";
import { label } from "./labels";
import type { TxType } from "./params";

type Category = Schemas["CategoryOut"];

export type Direction = "in" | "out";
export type PickerGroup = { value: string; label: string; items: Category[] };

/** Money out when any row goes out: a merchant item with purchases and refunds is labelled as a
 * purchase, and its refunds take the same category. */
export const directionOf = (amounts: (string | number)[]): Direction =>
  amounts.some((amount) => Number(amount) < 0) ? "out" : "in";

/** Money out never takes an income category (the API answers 422); money in takes any, because
 * a refund keeps its purchase's category. /review drops a jev suggestion that does not fit. */
export function fitsDirection(slug: string, categories: Category[], direction: Direction): boolean {
  const category = categories.find((c) => c.slug === slug);
  return category !== undefined && (direction === "in" || category.tx_type !== "income");
}

export function byLevel1(categories: Category[]): PickerGroup[] {
  const groups = new Map<string, Category[]>();
  for (const category of categories) groups.set(category.level1, [...(groups.get(category.level1) ?? []), category]);
  return [...groups].map(([value, items]) => ({ value, label: label(value), items }));
}

/** Money out: expense groups, then transfers. Money in: income first, then every expense category
 * as "Refund of a purchase", then transfers. Suggestions (jev's top scores) come first when they
 * fit the direction. */
export function pickerGroups(categories: Category[], direction: Direction, suggested: string[] = []): PickerGroup[] {
  const of = (type: string) => categories.filter((category) => category.tx_type === type);
  const main =
    direction === "out"
      ? [...byLevel1(of("expense")), ...byLevel1(of("transfer"))]
      : [
          ...byLevel1(of("income")),
          { value: "refund", label: "Refund of a purchase", items: of("expense") },
          ...byLevel1(of("transfer")),
        ];
  const allowed = new Map(main.flatMap((group) => group.items).map((category) => [category.slug, category]));
  const top = suggested.flatMap((slug) => allowed.get(slug) ?? []);
  return top.length ? [{ value: "suggested", label: "Suggested", items: top }, ...main] : main;
}

export type FilterOption = { kind: "group" | "category"; value: string; label: string };
export type FilterGroup = { value: string; label: string; items: FilterOption[] };

/** The explorer's "group or category" filter follows its type filter; each group starts with
 * "All of <group>". */
export function filterGroups(categories: Category[], txType?: TxType): FilterGroup[] {
  const shown = txType ? categories.filter((category) => category.tx_type === txType) : categories;
  return byLevel1(shown).map((group) => ({
    value: group.value,
    label: group.label,
    items: [
      { kind: "group", value: group.value, label: `All of ${group.label}` },
      ...group.items.map((category): FilterOption => ({ kind: "category", value: category.slug, label: label(category.slug) })),
    ],
  }));
}
