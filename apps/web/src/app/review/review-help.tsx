"use client";

import type { ToggleEvent } from "react";

import { FieldDescription } from "@/components/ui/field";
import type { Schemas } from "@/lib/api";
import { startingCategory } from "@/lib/pickers";

/** Every edit field has a one-line description (spec 7.2). /review says it once, above the cards,
 * and every card's fields point here with aria-describedby. */
export const HELP_ID = {
  merchant: "review-help-merchant",
  merchantOne: "review-help-merchant-one",
  category: "review-help-category",
  subscription: "review-help-subscription",
  line: "review-help-line",
  confidence: "review-help-confidence",
} as const;

type Item = Schemas["ReviewItem"];
type Category = Schemas["CategoryOut"];
/** `when` shows a line only for the cards that need it. */
type Line = { id: string; field: string; text: string; when?: (items: Item[], categories: Category[]) => boolean };

const STORAGE_KEY = "review-help:v1";
// The category fields only exist on category cards: a list of duplicate suggestions needs none of them.
const hasCategoryCards = (items: Item[]) => items.some((item) => item.kind !== "merge");

const LINES: Line[] = [
  // One line per card kind: a merchant's card renames or merges the merchant, while a transaction
  // reviewed on its own (with or without a merchant) only takes a merchant for itself.
  {
    id: HELP_ID.merchant,
    field: "Merchant",
    text: "who the money went to or came from; type a name to rename the merchant, or pick another one to merge them.",
    when: (items) => items.some((item) => item.kind === "merchant"),
  },
  {
    id: HELP_ID.merchantOne,
    field: "Merchant of a transaction reviewed on its own",
    text: "a name you type creates a merchant for it, and a pick assigns an existing one.",
    when: (items) => items.some((item) => item.kind === "transaction"),
  },
  {
    id: HELP_ID.category,
    field: "Category",
    text: "money out lists expenses and transfers; money in lists income first, then refunds under “Refund of a purchase · <group>”, then transfers.",
    when: hasCategoryCards,
  },
  { id: HELP_ID.subscription, field: "Subscription", text: "a recurring charge; only money out can be one.", when: hasCategoryCards },
  {
    id: HELP_ID.line,
    field: "Category for this transaction",
    text: "expand a merchant to label one transaction on its own.",
    when: hasCategoryCards,
  },
  {
    id: HELP_ID.confidence,
    field: "jev",
    text: "the percentage beside a category is how sure jev, the AI categorizer, is of its suggestion; it goes once you pick another category.",
    // Only where a card shows "jev N%": beside a suggestion it starts with (none under Decision H).
    when: (items, categories) =>
      items.some((item) => item.suggestion.confidence != null && startingCategory(item, categories) !== ""),
  },
];

/** A disclosure that starts open; closing it is remembered on this device (spec 9). */
export function ReviewHelp({ items, categories }: { items: Item[]; categories: Category[] }) {
  // Applied once the element is in the page: the server HTML is open, and reading storage during
  // render would not match it.
  function applyStored(node: HTMLDetailsElement | null) {
    try {
      if (node && localStorage.getItem(STORAGE_KEY) === "closed") node.open = false;
    } catch {
      // Storage can throw in private browsing: the help stays open.
    }
  }

  // The browser owns the open state; this only remembers it.
  function onToggle(event: ToggleEvent<HTMLDetailsElement>) {
    const isOpen = event.currentTarget.open;
    try {
      if (isOpen) localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, "closed");
    } catch {
      // Not remembered, which only means it opens again next visit.
    }
  }

  const lines = LINES.filter((line) => !line.when || line.when(items, categories));
  if (lines.length === 0) return null;
  return (
    <details ref={applyStored} open onToggle={onToggle}>
      <summary className="cursor-pointer text-sm font-medium">How to review</summary>
      <ul className="mt-1 flex flex-col gap-0.5">
        {lines.map((line) => (
          <li key={line.id}>
            <FieldDescription id={line.id}>
              <span className="font-medium text-foreground">{line.field}:</span> {line.text}
            </FieldDescription>
          </li>
        ))}
      </ul>
    </details>
  );
}
