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

/** The category a /review card starts with: jev's suggestion when it fits the item's direction,
 * else none (Decision H). The card shows jev's confidence only beside that suggestion. */
export function startingCategory(
  item: { suggestion: { category_slug: string | null }; transactions: { amount: string | number }[] },
  categories: Category[],
): string {
  const slug = item.suggestion.category_slug ?? "";
  return fitsDirection(slug, categories, directionOf(item.transactions.map((t) => t.amount))) ? slug : "";
}

export function byLevel1(categories: Category[]): PickerGroup[] {
  const groups = new Map<string, Category[]>();
  for (const category of categories) groups.set(category.level1, [...(groups.get(category.level1) ?? []), category]);
  return [...groups].map(([value, items]) => ({ value, label: label(value), items }));
}

/** Money out: expense groups, then transfers. Money in: income first, then the expense categories
 * as "Refund of a purchase · <group>", one group per expense group, then transfers. Suggestions
 * (jev's top scores) come first when they fit the direction. */
export function pickerGroups(categories: Category[], direction: Direction, suggested: string[] = []): PickerGroup[] {
  const of = (type: string) => categories.filter((category) => category.tx_type === type);
  const refunds = byLevel1(of("expense")).map((group) => ({
    ...group,
    value: `refund-${group.value}`,
    label: `Refund of a purchase · ${group.label}`,
  }));
  const main =
    direction === "out"
      ? [...byLevel1(of("expense")), ...byLevel1(of("transfer"))]
      : [...byLevel1(of("income")), ...refunds, ...byLevel1(of("transfer"))];
  const allowed = new Map(main.flatMap((group) => group.items).map((category) => [category.slug, category]));
  const top = suggested.flatMap((slug) => allowed.get(slug) ?? []);
  return top.length ? [{ value: "suggested", label: "Suggested", items: top }, ...main] : main;
}

export type FilterOption = { kind: "group" | "category"; value: string; label: string };
export type FilterGroup = { value: string; label: string; items: FilterOption[] };

/** The explorer's "group or category" filter follows its type filter; each group starts with
 * "All of <group>". Rows without a category are "uncategorized", as the detail pages link to them
 * (knownGroup, knownCategory): money out as a group of its own, money in as a category of Income.
 * All types list only the group, which matches those rows in both directions. */
export function filterGroups(categories: Category[], txType?: TxType): FilterGroup[] {
  const shown = txType ? categories.filter((category) => category.tx_type === txType) : categories;
  const groups: FilterGroup[] = byLevel1(shown).map((group) => ({
    value: group.value,
    label: group.label,
    items: [
      { kind: "group", value: group.value, label: `All of ${group.label}` },
      ...group.items.map((category): FilterOption => ({ kind: "category", value: category.slug, label: label(category.slug) })),
    ],
  }));
  const uncategorized = label("uncategorized");
  if (txType === "income") {
    groups.find((group) => group.value === "income")?.items.push({ kind: "category", value: "uncategorized", label: uncategorized });
  }
  if (txType === undefined || txType === "expense") {
    groups.push({ value: "uncategorized", label: uncategorized, items: [{ kind: "group", value: "uncategorized", label: uncategorized }] });
  }
  return groups;
}

/** The option the URL names: its category, else its group. A category the list lacks falls back to
 * its group only for "uncategorized" (the uncategorized group's page links with that category too);
 * any other, such as a hand-edited one, selects nothing rather than "All of <group>". */
export function selectedFilter(groups: FilterGroup[], level1?: string, category?: string): FilterOption | null {
  const options = groups.flatMap((group) => group.items);
  const exact = options.find((option) => option.kind === "category" && option.value === category);
  if (exact) return exact;
  if (category !== undefined && category !== "uncategorized") return null;
  return options.find((option) => option.kind === "group" && option.value === level1) ?? null;
}
