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
  },
  { id: HELP_ID.subscription, field: "Subscription", text: "a recurring charge; only money out can be one." },
  { id: HELP_ID.line, field: "Category for this transaction", text: "expand a merchant to label one transaction on its own." },
  {
    id: HELP_ID.confidence,
    field: "jev",
    text: "the percentage beside a category is how sure jev, the AI categorizer, is of its suggestion; it goes once you pick another category.",
    // Only where a card shows "jev N%": beside a suggestion it starts with (none under Decision H).
    when: (items, categories) =>
      items.some((item) => item.suggestion.confidence != null && startingCategory(item, categories) !== ""),
  },
];

export function ReviewHelp({ items, categories }: { items: Item[]; categories: Category[] }) {
  return (
    <section aria-labelledby="review-help-title" className="flex flex-col gap-1">
      <h2 id="review-help-title" className="text-sm font-medium">
        How to review
      </h2>
      <ul className="flex flex-col gap-0.5">
        {LINES.filter((line) => !line.when || line.when(items, categories)).map((line) => (
          <li key={line.id}>
            <FieldDescription id={line.id}>
              <span className="font-medium text-foreground">{line.field}:</span> {line.text}
            </FieldDescription>
          </li>
        ))}
      </ul>
    </section>
  );
}
