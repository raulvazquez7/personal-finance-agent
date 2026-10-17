/** Names shown for categories, groups, breakdown rows, sources and account selections. Categories
 * are data (supabase/seed/categories.yaml): their names come from GET /categories (spec 8.1), and
 * a slug without one reads as itself (label). */

import type { Schemas } from "./api";
import type { Source, TxType } from "./params";

type Category = Schemas["CategoryOut"];
type Row = Schemas["BreakdownRow"];

export type Dimension = "group" | "category" | "merchant";

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** "restaurants_bars" reads "Restaurants bars"; a row without a category is "Uncategorized". */
export function label(slug: string | null | undefined): string {
  return slug ? capitalize(slug.replaceAll("_", " ")) : "Uncategorized";
}

/** The stored name of a category (spec 8.1), or its readable slug. */
export function categoryName(slug: string | null | undefined, categories: Category[]): string {
  return categories.find((c) => c.slug === slug)?.name ?? label(slug);
}

/** The stored name of a group, read from any of its categories, or its readable slug. */
export function groupName(level1: string | null | undefined, categories: Category[]): string {
  return categories.find((c) => c.level1 === level1)?.group_name ?? label(level1);
}

export const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** The line under a group's name: its first categories, by name ("Rent, Mortgage, Utilities…"). */
export function groupHint(level1: string, categories: Category[]): string {
  if (level1 === "credit_card") return "Not itemized: card statements are not imported";
  if (level1 === "uncategorized") return "Not categorized yet"; // these rows never reach /review
  const names = categories.filter((c) => c.level1 === level1).map((c) => c.name);
  if (names.length === 0) return "";
  const text = names.slice(0, 3).join(", ");
  return names.length > 3 ? `${text}…` : text;
}

/** The API's folded row names its dimension ("Other groups", "Other categories", "Other 12
 * merchants"), so it never reads like the expense group "other" ("Other"). The overview's Groups
 * view has no folded row; any dimension may still send one. */
export function rowName(row: Row, dimension: Dimension, categories: Category[]): string {
  if (row.key === "_other") {
    if (dimension === "merchant") return `Other ${plural(row.folded ?? 0, "merchant", "merchants")}`;
    return dimension === "group" ? "Other groups" : "Other categories";
  }
  // A merchant row without a merchant is keyed "category:<slug>"; its hint names the category.
  if (dimension === "merchant") return row.label ?? "No merchant";
  return dimension === "group" ? groupName(row.key, categories) : categoryName(row.key, categories);
}

export function rowHint(row: Row, dimension: Dimension, categories: Category[]): string {
  if (row.key === "_other") {
    if (dimension === "merchant") return "";
    const folded = row.folded ?? 0;
    return dimension === "group" ? plural(folded, "group", "groups") : plural(folded, "category", "categories");
  }
  if (dimension === "group") {
    // The row's own top categories, in that order. The taxonomy line is only the fallback.
    if (row.top_categories.length > 0) {
      return row.top_categories.map((slug) => categoryName(slug, categories)).join(", ");
    }
    return groupHint(row.key, categories);
  }
  if (dimension === "category") return groupName(row.level1, categories);
  if (row.category_count > 1) {
    return `${plural(row.category_count, "category", "categories")} · ${plural(row.count, "transaction", "transactions")}`;
  }
  return `${categoryName(row.category_slug, categories)} · ${plural(row.count, "transaction", "transactions")}`;
}

// Keyed by params.ts's SOURCES, the one list of sources: a source without a name fails the build.
const SOURCE_LABELS: Record<Source, string> = { rule: "Rule", merchant: "Merchant", jev: "AI (jev)", user: "You", none: "Pending" };

/** Who categorized a row (spec 7.3). */
export const sourceLabel = (source: Source) => SOURCE_LABELS[source];

export function accountsLabel(ids: string[], accounts: { id: string; name: string }[]): string {
  if (ids.length === 0) return "All accounts";
  if (ids.length === 1) return accounts.find((account) => account.id === ids[0])?.name ?? "1 account";
  return `${ids.length} accounts`;
}

/** What stands before an account's last four digits, as the importer writes its default name
 * ("<bank> ····1234"). Every place that shows the digits uses it. */
export const DIGITS_SEPARATOR = "····";

/** "····1234" after an account's name, unless the name already carries those digits (the
 * importer's default name does). */
export const accountDigits = (account: { name: string; iban_last4: string }) =>
  account.name.includes(account.iban_last4) ? null : `${DIGITS_SEPARATOR}${account.iban_last4}`;

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
