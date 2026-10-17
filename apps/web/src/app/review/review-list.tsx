"use client";

import { CheckCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Progress } from "@/components/ui/progress";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { apiPatch, apiPost, type Schemas } from "@/lib/api";
import { plural } from "@/lib/labels";
import { directionOf } from "@/lib/pickers";
import { reviewOrder, type ReviewFilter, type ReviewSort } from "@/lib/review-order";
import { settledByConfirm, settledByMerge } from "@/lib/review-settled";

import { MergeCard } from "./merge-card";
import { ReviewHelp } from "./review-help";
import { ReviewRow, type Decision } from "./review-row";
import { useSkipped } from "./use-skipped";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];
/** The change a row is waiting to send; `id` is also its toast's id. */
type Pending = { id: string; timer: ReturnType<typeof setTimeout>; commit: (keepalive: boolean) => void };

const UNDO_MS = 5000;
let seq = 0;

type Props = {
  initialItems: Item[];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  /** The header's numbers; `uncategorized` counts transactions no categorization run has handled
   * yet (no jev key, or jev failed on them). */
  count: Schemas["ReviewCount"];
};

export function ReviewList({ initialItems, categories, merchants, count }: Props) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [total] = useState(initialItems.length);
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [sort, setSort] = useState<ReviewSort>("amount");
  const [skipped, skip] = useSkipped();
  const pending = useRef(new Map<string, Pending>()); // by row key: at most one change per row
  const { uncategorized } = count;

  useEffect(() => {
    // Leaving the page, or the route, sends what is still waiting for its undo window.
    const waiting = pending.current;
    const flush = () => waiting.forEach(({ timer, commit }) => { clearTimeout(timer); commit(true); });
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      flush();
    };
  }, []);

  // The order is chosen at render time (reviewOrder): the list only adds and removes cards.
  function replace(key: string, next: Item | null) {
    setItems((current) => {
      const others = current.filter((item) => item.key !== key);
      return next ? [...others, next] : others;
    });
  }

  function sendNow(key: string) {
    const earlier = pending.current.get(key);
    if (earlier) {
      clearTimeout(earlier.timer);
      earlier.commit(false);
    }
  }

  function schedule(
    original: Item,
    next: Item | null,
    message: string,
    send: (keepalive: boolean) => Promise<void>,
    settled: Item[] = [],
  ) {
    // A new change on a row sends that row's earlier change first, so Undo never restores a stale
    // row. The cards this change settles count as those rows.
    sendNow(original.key);
    settled.forEach((card) => sendNow(card.key));
    // Cards the change settles on the server (a survivor's own item, inputs topic 6, or a merged
    // source's cards) leave the page with it, and Undo or a failed send brings them all back.
    const restore = () => {
      replace(original.key, original);
      settled.forEach((card) => replace(card.key, card));
    };
    replace(original.key, next);
    settled.forEach((card) => replace(card.key, null));
    const id = `${original.key}:${++seq}`;
    const commit = (keepalive: boolean) => {
      pending.current.delete(original.key);
      // The toast can outlive the timer (sonner pauses on hover): no Undo once the change is sent.
      toast.dismiss(id);
      send(keepalive).then(
        // The root layout does not re-render on client navigation: refresh its badge count.
        () => router.refresh(),
        () => {
          toast.error("Could not save that change.");
          restore();
        },
      );
    };
    const timer = setTimeout(() => commit(false), UNDO_MS);
    pending.current.set(original.key, { id, timer, commit });
    toast(message, {
      id,
      duration: UNDO_MS,
      action: {
        label: "Undo",
        onClick: () => {
          if (pending.current.get(original.key)?.id !== id) return;
          clearTimeout(timer);
          pending.current.delete(original.key);
          restore();
        },
      },
    });
  }

  function confirm(item: Item, d: Decision) {
    if (item.kind === "merchant" && item.merchant) {
      const merchantId = item.merchant.id;
      const mergeInto = d.merchant?.id && d.merchant.id !== merchantId ? d.merchant.id : null;
      const body = {
        category_slug: d.categorySlug,
        // Money in has no subscription switch: null keeps the merchant's flag and its rows' marks.
        is_subscription: directionOf(item.transactions.map((t) => t.amount)) === "in" ? null : d.isSubscription,
        name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
        merge_into_id: mergeInto,
      };
      schedule(item, null, "Confirmed", (keepalive) => apiPost(`/merchants/${merchantId}/review`, body, { keepalive }),
        settledByConfirm(items, item, mergeInto));
    } else {
      labelOne(item, item.transactions[0], d, "Confirmed");
    }
  }

  function mergeYes(item: Item, source: Schemas["MerchantOut"], into: Schemas["MergeSuggestion"]) {
    // The source's other cards and the duplicate cards that suggest it leave with it.
    schedule(item, null, "Merged", (keepalive) =>
      apiPatch(`/merchants/${source.id}`, { merge_into_id: into.merchant_id }, { keepalive }), settledByMerge(items, item));
  }

  function mergeNo(item: Item, source: Schemas["MerchantOut"]) {
    schedule(item, null, "Dismissed", (keepalive) =>
      apiPost(`/merchants/${source.id}/dismiss-merge`, undefined, { keepalive }));
  }

  function labelOne(item: Item, tx: Transaction, d: Decision, message: string) {
    const rest = item.transactions.filter((t) => t.id !== tx.id);
    const next = rest.length
      ? { ...item, transactions: rest, count: rest.length,
          total: String(rest.reduce((sum, t) => sum + Number(t.amount), 0)) }
      : null;
    const body = {
      category_slug: d.categorySlug,
      is_subscription: d.isSubscription,
      merchant_id: d.merchant?.id ?? null,
      new_merchant_name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
    };
    schedule(item, next, message, (keepalive) =>
      apiPost(`/transactions/${tx.id}/label`, body, { keepalive }));
  }

  const done = Math.max(total - items.length, 0);
  const shown = reviewOrder(items, filter, sort, skipped);
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight">Review</h1>
          {total > 0 && <span className="text-sm tabular-nums text-muted-foreground">{done} of {total}</span>}
        </div>
        {count.pending > 0 && (
          <p className="text-sm">
            {count.pending} to review: {plural(count.categories, "category", "categories")} ·{" "}
            {plural(count.merges, "possible duplicate", "possible duplicates")}
          </p>
        )}
        <p className="text-sm text-muted-foreground">Confirm or fix. Your answer applies to every transaction of the merchant.</p>
        {items.length > 0 && <ReviewHelp items={items} categories={categories} />}
        {uncategorized > 0 && (
          <p className="text-sm text-muted-foreground">
            {plural(uncategorized, "transaction is", "transactions are")} not categorized yet. Each import starts a
            categorization run in the background: give it a minute and reload this page before starting another run.
            If they stay, the API console says why (“jev skipped” when no jev key is set).
          </p>
        )}
        {total > 0 && <Progress aria-label="Review progress" value={(done / total) * 100} />}
        {items.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup
              variant="segment"
              size="sm"
              aria-label="Show"
              value={[filter]}
              onValueChange={(value: string[]) => value[0] && setFilter(value[0] as ReviewFilter)}
            >
              <ToggleGroupItem value="all">All</ToggleGroupItem>
              <ToggleGroupItem value="categories">Categories</ToggleGroupItem>
              <ToggleGroupItem value="duplicates">Duplicates</ToggleGroupItem>
            </ToggleGroup>
            <ToggleGroup
              variant="segment"
              size="sm"
              aria-label="Sort by"
              className="ml-auto"
              value={[sort]}
              onValueChange={(value: string[]) => value[0] && setSort(value[0] as ReviewSort)}
            >
              <ToggleGroupItem value="amount">Amount</ToggleGroupItem>
              <ToggleGroupItem value="date">Date</ToggleGroupItem>
            </ToggleGroup>
          </div>
        )}
      </header>

      {items.length === 0 ? (
        uncategorized === 0 && (
          <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
            <CheckCircle2 className="size-8" />
            <p>All caught up</p>
          </div>
        )
      ) : shown.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Nothing to review under this filter.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {shown.map((item) => {
            const { merchant, merge } = item;
            if (item.kind === "merge" && merchant && merge) {
              return (
                <MergeCard
                  key={item.key}
                  item={item}
                  onYes={() => mergeYes(item, merchant, merge)}
                  onNo={() => mergeNo(item, merchant)}
                  onSkip={() => skip(item.key)}
                />
              );
            }
            return (
              <ReviewRow
                key={item.key}
                item={item}
                categories={categories}
                merchants={merchants}
                onConfirm={(d) => confirm(item, d)}
                onLabelOne={(tx, d) => labelOne(item, tx, d, "Labelled")}
                onSkip={() => skip(item.key)}
              />
            );
          })}
        </ul>
      )}
    </section>
  );
}
