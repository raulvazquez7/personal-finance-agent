"use client";

import { ArrowDownLeft, ArrowUpRight, Check, ChevronRight } from "lucide-react";
import { useId, useState } from "react";

import { NoData } from "@/components/money/no-data";
import { CategoryPicker } from "@/components/pickers/category-picker";
import { MerchantPicker, type MerchantChoice } from "@/components/pickers/merchant-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { Schemas } from "@/lib/api";
import { dayLong, signedMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { directionOf, fitsDirection } from "@/lib/pickers";
import { cn } from "@/lib/utils";

import { HELP_ID } from "./review-help";

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
  const direction = directionOf(item.transactions.map((t) => t.amount));
  // Decision H: a jev suggestion that does not fit the direction (income on money out) is dropped.
  const suggested = suggestion.category_slug ?? "";
  const [categorySlug, setCategorySlug] = useState(fitsDirection(suggested, categories, direction) ? suggested : "");
  const [isSubscription, setIsSubscription] = useState(suggestion.is_subscription);
  // Only money out is a subscription (spec 6): money in never shows or sends one.
  const subscription = isSubscription && direction === "out";
  const [merchant, setMerchant] = useState<MerchantChoice | null>(item.merchant ?? null);
  const [open, setOpen] = useState(false);
  const level1 = categories.find((c) => c.slug === categorySlug)?.level1;
  const showConfidence = categorySlug === suggestion.category_slug && suggestion.confidence != null;
  const single = item.count < 2 ? item.transactions[0] : null;
  // Merge only picks the suggested merchant: confirming then merges and sets the category in one request.
  const mergePicked = merge != null && merchant?.id === merge.merchant_id;
  const incoming = item.transactions.some((t) => Number(t.amount) > 0);
  const outgoing = item.transactions.some((t) => Number(t.amount) < 0);
  const description = item.transactions[0].description_raw;
  const labelId = useId();

  return (
    <li>
      {/* A group named by its bank text: every card repeats Merchant, Category and Confirm. */}
      <div role="group" aria-labelledby={labelId} className="flex flex-col gap-3 rounded-card bg-card p-4">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          disabled={item.count < 2}
          aria-expanded={item.count > 1 ? open : undefined}
          className="flex min-w-0 items-center gap-2 text-left text-sm text-muted-foreground"
        >
          <ChevronRight className={cn("size-4 shrink-0 transition-transform", open && "rotate-90", item.count < 2 && "invisible")} />
          <Direction incoming={incoming} outgoing={outgoing} />
          {single && (
            <span className="shrink-0">
              {dayLong(single.booked_at)}
              {/* On phones the account would push the amount off the row. */}
              <span className="hidden sm:inline"> · {single.account_name}</span>
            </span>
          )}
          {/* Two lines and a title, so the bank text can always be read on a phone (dogfood issue 003). */}
          <span id={labelId} className="line-clamp-2 min-w-0 break-words" title={description}>
            {description}
          </span>
          {item.count > 1 && <span className="shrink-0">×{item.count}</span>}
          <Amount value={Number(item.total)} className="ml-auto shrink-0 font-medium" />
        </button>

        <div className="grid gap-3 md:grid-cols-[1fr_1fr_7rem_auto_auto] md:items-center">
          <MerchantPicker
            merchants={merchants}
            value={merchant}
            onChange={setMerchant}
            ariaDescribedBy={item.kind === "merchant" ? HELP_ID.merchant : HELP_ID.merchantOne}
          />
          <div className="flex items-center gap-2">
            <CategoryPicker
              categories={categories}
              direction={direction}
              suggested={suggestion.top.map((score) => score.slug)}
              value={categorySlug}
              onChange={setCategorySlug}
              ariaDescribedBy={HELP_ID.category}
            />
            {/* jev's confidence in its own suggestion, as text (the "How to review" block explains it). */}
            {showConfidence && (
              <span className="shrink-0 text-xs whitespace-nowrap text-muted-foreground">
                {`jev ${Math.round((suggestion.confidence ?? 0) * 100)}%`}
              </span>
            )}
          </div>
          <span className="truncate text-sm text-muted-foreground">{level1 ? label(level1) : <NoData />}</span>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch
              checked={subscription}
              disabled={direction === "in"}
              onCheckedChange={(checked) => setIsSubscription(checked)}
              aria-describedby={HELP_ID.subscription}
            />
            Subscription
          </label>
          {/* With several transactions, say that the answer covers all of them, not the first line. */}
          <Button
            size={single ? "icon" : "default"}
            aria-label={single ? "Confirm" : undefined}
            disabled={!categorySlug}
            onClick={() => onConfirm({ categorySlug, isSubscription: subscription, merchant })}
          >
            <Check />
            {!single && `Apply to all ${item.count}`}
          </Button>
        </div>

        {merge && (
          <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
            {mergePicked ? (
              <span>
                Confirm to merge into <strong>{merge.name}</strong>.
              </span>
            ) : (
              <>
                <span>
                  Same merchant as <strong>{merge.name}</strong>?
                </span>
                <Button size="sm" variant="outline" className="ml-auto" onClick={() => setMerchant({ id: merge.merchant_id, name: merge.name })}>
                  Merge
                </Button>
                <Button size="sm" variant="ghost" onClick={onDismissMerge}>
                  No
                </Button>
              </>
            )}
          </div>
        )}

        {open && (
          <ul className="flex flex-col divide-y border-t">
            {item.transactions.map((tx) => (
              <TransactionLine
                key={tx.id}
                tx={tx}
                categories={categories}
                initial={categorySlug}
                initialSubscription={subscription}
                onLabel={(decision) => onLabelOne(tx, decision)}
              />
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

function TransactionLine({
  tx,
  categories,
  initial,
  initialSubscription,
  onLabel,
}: {
  tx: Transaction;
  categories: Schemas["CategoryOut"][];
  initial: string;
  initialSubscription: boolean;
  onLabel: (decision: Decision) => void;
}) {
  const [slug, setSlug] = useState(initial);
  const [subscription, setSubscription] = useState(initialSubscription);
  const outgoing = Number(tx.amount) < 0;
  return (
    <li className="grid gap-2 py-2 text-sm md:grid-cols-[6.5rem_minmax(0,1fr)_minmax(0,1fr)_auto_auto] md:items-center">
      <span className="text-muted-foreground">{dayLong(tx.booked_at)}</span>
      {/* Each line shows its own bank text: one merchant can carry different charges (dogfood issue 002). */}
      <span className="flex min-w-0 flex-col">
        <span className="line-clamp-2 break-words" title={tx.description_raw}>
          {tx.description_raw}
        </span>
        <span className="text-muted-foreground">
          <Amount value={Number(tx.amount)} /> · {tx.account_name}
        </span>
      </span>
      <CategoryPicker
        categories={categories}
        direction={directionOf([tx.amount])}
        value={slug}
        onChange={setSlug}
        ariaLabel="Category for this transaction"
        ariaDescribedBy={`${HELP_ID.line} ${HELP_ID.category}`}
      />
      <Switch
        checked={subscription && outgoing}
        disabled={!outgoing}
        onCheckedChange={(checked) => setSubscription(checked)}
        aria-label="Subscription"
        aria-describedby={HELP_ID.subscription}
      />
      <Button
        size="sm"
        variant="outline"
        disabled={!slug}
        onClick={() => onLabel({ categorySlug: slug, isSubscription: subscription && outgoing, merchant: null })}
      >
        <Check data-icon="inline-start" />
        Only this one
      </Button>
    </li>
  );
}

/** Money in or out at a glance, beyond the sign: a refund must not read as a purchase. */
function Direction({ incoming, outgoing }: { incoming: boolean; outgoing: boolean }) {
  if (incoming && outgoing) return <Badge variant="outline">Money in and out</Badge>;
  return incoming ? (
    <Badge variant="outline" className="text-income">
      <ArrowDownLeft />
      Money in
    </Badge>
  ) : (
    <Badge variant="outline">
      <ArrowUpRight />
      Money out
    </Badge>
  );
}

function Amount({ value, className }: { value: number; className?: string }) {
  return <span className={cn("text-foreground", value > 0 && "text-income", className)}>{signedMoney(value)}</span>;
}
