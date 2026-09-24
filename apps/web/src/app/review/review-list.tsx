"use client";

import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Progress } from "@/components/ui/progress";
import { apiPost, type Schemas } from "@/lib/api";

import { ReviewRow, type Decision } from "./review-row";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];
/** The change a row is waiting to send; `id` is also its toast's id. */
type Pending = { id: string; timer: ReturnType<typeof setTimeout>; commit: (keepalive: boolean) => void };

const UNDO_MS = 5000;
let seq = 0;
const byTotal = (a: Item, b: Item) => Math.abs(Number(b.total)) - Math.abs(Number(a.total));

type Props = {
  initialItems: Item[];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
};

export function ReviewList({ initialItems, categories, merchants }: Props) {
  const [items, setItems] = useState(initialItems);
  const [total] = useState(initialItems.length);
  const pending = useRef(new Map<string, Pending>()); // by row key: at most one change per row

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

  function replace(key: string, next: Item | null) {
    setItems((current) => {
      const others = current.filter((item) => item.key !== key);
      return (next ? [...others, next] : others).sort(byTotal);
    });
  }

  function schedule(
    original: Item,
    next: Item | null,
    message: string,
    send: (keepalive: boolean) => Promise<void>,
  ) {
    // A new change on the same row sends the earlier one first, so Undo never restores a stale row.
    const earlier = pending.current.get(original.key);
    if (earlier) {
      clearTimeout(earlier.timer);
      earlier.commit(false);
    }
    replace(original.key, next);
    const id = `${original.key}:${++seq}`;
    const commit = (keepalive: boolean) => {
      pending.current.delete(original.key);
      // The toast can outlive the timer (sonner pauses on hover): no Undo once the change is sent.
      toast.dismiss(id);
      send(keepalive).catch(() => {
        toast.error("Could not save that change.");
        replace(original.key, original);
      });
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
          replace(original.key, original);
        },
      },
    });
  }

  function confirm(item: Item, d: Decision) {
    if (item.kind === "merchant" && item.merchant) {
      const merchantId = item.merchant.id;
      const body = {
        category_slug: d.categorySlug,
        is_subscription: d.isSubscription,
        name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
        merge_into_id: d.merchant?.id && d.merchant.id !== merchantId ? d.merchant.id : null,
      };
      schedule(item, null, "Confirmed", (keepalive) =>
        apiPost(`/merchants/${merchantId}/review`, body, { keepalive }));
    } else {
      labelOne(item, item.transactions[0], d, "Confirmed");
    }
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
  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight">Review</h1>
          {total > 0 && <span className="text-sm tabular-nums text-muted-foreground">{done} of {total}</span>}
        </div>
        <p className="text-sm text-muted-foreground">Confirm or fix. Your answer applies to every transaction of the merchant.</p>
        {total > 0 && <Progress value={(done / total) * 100} />}
      </header>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
          <CheckCircle2 className="size-8" />
          <p>All caught up</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <ReviewRow
              key={item.key}
              item={item}
              categories={categories}
              merchants={merchants}
              onConfirm={(d) => confirm(item, d)}
              onLabelOne={(tx, d) => labelOne(item, tx, d, "Labelled")}
              onMerge={() => item.merge && item.merchant && schedule(item, null, "Merged", (keepalive) =>
                apiPost(`/merchants/${item.merchant!.id}/merge`, { into_id: item.merge!.merchant_id }, { keepalive }))}
              onDismissMerge={() => item.merchant && schedule(item, { ...item, merge: null }, "Dismissed", (keepalive) =>
                apiPost(`/merchants/${item.merchant!.id}/dismiss-merge`, undefined, { keepalive }))}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
