"use client";

import { ArrowDownLeft, ArrowUpRight, Check, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { signedEuro, type Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

import { CategoryPicker } from "./category-picker";
import { MerchantPicker, type MerchantChoice } from "./merchant-picker";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];

export type Decision = { categorySlug: string; isSubscription: boolean; merchant: MerchantChoice | null };

type Props = {
  item: Item;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  onConfirm: (decision: Decision) => void;
  onLabelOne: (tx: Transaction, decision: Decision) => void;
  onDismissMerge: () => void;
};

export function ReviewRow({ item, categories, merchants, onConfirm, onLabelOne, onDismissMerge }: Props) {
  const { suggestion, merge } = item;
  const [categorySlug, setCategorySlug] = useState(suggestion.category_slug ?? "");
  const [isSubscription, setIsSubscription] = useState(suggestion.is_subscription);
  const [merchant, setMerchant] = useState<MerchantChoice | null>(item.merchant ?? null);
  const [open, setOpen] = useState(false);
  const level1 = categories.find((c) => c.slug === categorySlug)?.level1;
  const showConfidence = categorySlug === suggestion.category_slug && suggestion.confidence != null;
  const single = item.count < 2 ? item.transactions[0] : null;
  // Merge only picks the suggested merchant: confirming then merges and sets the category in one request.
  const mergePicked = merge != null && merchant?.id === merge.merchant_id;
  const incoming = item.transactions.some((t) => Number(t.amount) > 0);
  const outgoing = item.transactions.some((t) => Number(t.amount) < 0);

  return (
    <li className={cn("flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs",
                      incoming && !outgoing && "border-l-4 border-l-green-600")}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={item.count < 2}
        className="flex min-w-0 items-center gap-2 text-left text-sm text-muted-foreground"
      >
        <ChevronRight className={cn("size-4 shrink-0 transition-transform", open && "rotate-90", item.count < 2 && "invisible")} />
        <Direction incoming={incoming} outgoing={outgoing} />
        {single && (
          <span className="shrink-0 tabular-nums">
            {single.booked_at}
            {/* On phones the account would push the amount off the row. */}
            <span className="hidden sm:inline"> · {single.account_name}</span>
          </span>
        )}
        <span className="truncate">{item.transactions[0].description_raw}</span>
        {item.count > 1 && <span className="shrink-0 tabular-nums">×{item.count}</span>}
        <Amount value={Number(item.total)} className="ml-auto shrink-0 font-medium" />
      </button>

      <div className="grid gap-3 md:grid-cols-[1fr_1fr_7rem_auto_auto] md:items-center">
        <MerchantPicker merchants={merchants} value={merchant} onChange={setMerchant} />
        <div className="flex items-center gap-2">
          <CategoryPicker categories={categories} suggested={suggestion.top} value={categorySlug} onChange={setCategorySlug} />
          {showConfidence && (
            <span className="text-xs tabular-nums text-muted-foreground" title="jev confidence">
              ·{Math.round((suggestion.confidence ?? 0) * 100)}
            </span>
          )}
        </div>
        <span className="truncate text-sm text-muted-foreground">{level1 ?? "—"}</span>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Switch checked={isSubscription} onCheckedChange={(checked) => setIsSubscription(checked)} />
          Subscription
        </label>
        {/* With several transactions, say that the answer covers all of them, not the first line. */}
        <Button size={single ? "icon" : "default"} aria-label={single ? "Confirm" : undefined}
                disabled={!categorySlug} onClick={() => onConfirm({ categorySlug, isSubscription, merchant })}>
          <Check />
          {!single && `Apply to all ${item.count}`}
        </Button>
      </div>

      {merge && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          {mergePicked ? (
            <span>Confirm to merge into <strong>{merge.name}</strong>.</span>
          ) : (
            <>
              <span>Same merchant as <strong>{merge.name}</strong>?</span>
              <Button size="sm" variant="secondary" className="ml-auto"
                      onClick={() => setMerchant({ id: merge.merchant_id, name: merge.name })}>
                Merge
              </Button>
              <Button size="sm" variant="ghost" onClick={onDismissMerge}>No</Button>
            </>
          )}
        </div>
      )}

      {open && (
        <ul className="flex flex-col divide-y border-t">
          {item.transactions.map((tx) => (
            <TransactionLine key={tx.id} tx={tx} categories={categories} initial={categorySlug}
                             initialSubscription={isSubscription}
                             onLabel={(decision) => onLabelOne(tx, decision)} />
          ))}
        </ul>
      )}
    </li>
  );
}

function TransactionLine({ tx, categories, initial, initialSubscription, onLabel }: {
  tx: Transaction;
  categories: Schemas["CategoryOut"][];
  initial: string;
  initialSubscription: boolean;
  onLabel: (decision: Decision) => void;
}) {
  const [slug, setSlug] = useState(initial);
  const [subscription, setSubscription] = useState(initialSubscription);
  return (
    <li className="grid gap-2 py-2 text-sm md:grid-cols-[6rem_1fr_1fr_auto_auto] md:items-center">
      <span className="tabular-nums text-muted-foreground">{tx.booked_at}</span>
      <span className="truncate"><Amount value={Number(tx.amount)} /> · {tx.account_name}</span>
      <CategoryPicker categories={categories} suggested={[]} value={slug} onChange={setSlug} />
      <Switch checked={subscription} onCheckedChange={(checked) => setSubscription(checked)} aria-label="Subscription" />
      <Button size="sm" variant="outline" disabled={!slug}
              onClick={() => onLabel({ categorySlug: slug, isSubscription: subscription, merchant: null })}>
        <Check />
        Only this one
      </Button>
    </li>
  );
}

/** Money in or out at a glance, beyond the sign: a refund must not read as a purchase. */
function Direction({ incoming, outgoing }: { incoming: boolean; outgoing: boolean }) {
  if (incoming && outgoing) return <Badge variant="outline">Money in and out</Badge>;
  return incoming ? (
    <Badge variant="outline" className="border-green-600/40 bg-green-50 text-green-700"><ArrowDownLeft />Money in</Badge>
  ) : (
    <Badge variant="outline"><ArrowUpRight />Money out</Badge>
  );
}

function Amount({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("tabular-nums text-foreground", value > 0 && "text-green-700", className)}>
      {signedEuro.format(value)}
    </span>
  );
}
