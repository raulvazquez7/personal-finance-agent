import { FieldDescription } from "@/components/ui/field";

/** Every edit field has a one-line description (spec 7.2). /review says it once, above the cards,
 * and every card's fields point here with aria-describedby. */
export const HELP_ID = {
  merchant: "review-help-merchant",
  category: "review-help-category",
  subscription: "review-help-subscription",
  line: "review-help-line",
} as const;

const LINES = [
  { id: HELP_ID.merchant, field: "Merchant", text: "who the money went to or came from; type a name to rename it, or pick an existing merchant to merge." },
  { id: HELP_ID.category, field: "Category", text: 'money out lists expenses and transfers; money in lists income first, then refunds under "Refund of a purchase".' },
  { id: HELP_ID.subscription, field: "Subscription", text: "a recurring charge; only money out can be one." },
  { id: HELP_ID.line, field: "Category for this transaction", text: "expand a merchant to label one transaction on its own." },
];

export function ReviewHelp() {
  return (
    <section aria-labelledby="review-help-title" className="flex flex-col gap-1">
      <h2 id="review-help-title" className="text-sm font-medium">
        How to review
      </h2>
      <ul className="flex flex-col gap-0.5">
        {LINES.map((line) => (
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
