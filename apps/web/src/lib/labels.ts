/** Names shown for slugs, breakdown rows, sources and account selections. Categories are data
 * (supabase/seed/categories.yaml), so their names come from their slugs. */

import type { Schemas } from "./api";
import type { TxType } from "./params";

type Category = Schemas["CategoryOut"];
type Row = Schemas["BreakdownRow"];

export type Dimension = "group" | "category" | "merchant";

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** "restaurants_bars" reads "Restaurants bars"; a row without a category is "Uncategorized". */
export function label(slug: string | null | undefined): string {
  return slug ? capitalize(slug.replaceAll("_", " ")) : "Uncategorized";
}

export const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** The line under a group's name: its first categories (mockup: "Rent, utilities, internet"). */
export function groupHint(level1: string, categories: Category[]): string {
  if (level1 === "credit_card") return "Not itemized: card statements are not imported";
  if (level1 === "uncategorized") return "Not categorized yet"; // these rows never reach /review
  const names = categories.filter((c) => c.level1 === level1).map((c) => c.slug.replaceAll("_", " "));
  if (names.length === 0) return "";
  const text = capitalize(names.slice(0, 3).join(", "));
  return names.length > 3 ? `${text}…` : text;
}

export function rowName(row: Row, dimension: Dimension): string {
  if (row.key === "_other") {
    return dimension === "merchant" ? `Other ${plural(row.folded ?? 0, "merchant", "merchants")}` : "Other";
  }
  // A merchant row without a merchant is keyed "category:<slug>" and reads as its category.
  return dimension === "merchant" ? (row.label ?? label(row.category_slug)) : label(row.key);
}

export function rowHint(row: Row, dimension: Dimension, categories: Category[]): string {
  if (row.key === "_other") {
    if (dimension === "merchant") return "";
    const folded = row.folded ?? 0;
    return dimension === "group" ? plural(folded, "group", "groups") : plural(folded, "category", "categories");
  }
  if (dimension === "group") return groupHint(row.key, categories);
  if (dimension === "category") return label(row.level1);
  return `${label(row.category_slug)} · ${plural(row.count, "transaction", "transactions")}`;
}

const SOURCES: Record<string, string> = { rule: "Rule", merchant: "Merchant", jev: "AI (jev)", user: "You", none: "Pending" };

/** Who categorized a row (spec 7.3). */
export const sourceLabel = (source: string) => SOURCES[source] ?? source;

export function accountsLabel(ids: string[], accounts: { id: string; name: string }[]): string {
  if (ids.length === 0) return "All accounts";
  if (ids.length === 1) return accounts.find((account) => account.id === ids[0])?.name ?? "1 account";
  return `${ids.length} accounts`;
}

/** A group in the URL must exist, or the page is a 404, never an empty page. */
export function knownGroup(level1: string, categories: Category[]): boolean {
  return level1 === "uncategorized" || categories.some((c) => c.tx_type === "expense" && c.level1 === level1);
}

export function knownCategory(slug: string, categories: Category[], where: { type: TxType; level1?: string }): boolean {
  // Rows without a category: money out sits in the "uncategorized" group, money in in Income.
  if (slug === "uncategorized" && (where.level1 === "uncategorized" || where.type === "income")) return true;
  return categories.some(
    (c) => c.slug === slug && c.tx_type === where.type && (where.level1 === undefined || c.level1 === where.level1),
  );
}
