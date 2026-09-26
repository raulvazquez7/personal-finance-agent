"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TransactionTable } from "@/components/transactions/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { apiGet, type Schemas } from "@/lib/api";
import { applyChange } from "@/lib/transactions";

import { TransactionPanel } from "./transaction-panel";

type Tx = Schemas["Transaction"];

type Props = {
  initial: Schemas["TransactionPage"];
  search: string;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
};

/** The explorer's rows, grouped by day, 100 at a time (spec 7.3); clicking a row opens the side
 * panel. The next pages are fetched by the browser with the page's own query plus the cursor. */
export function TransactionList({ initial, search, categories, merchants }: Props) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Tx | null>(null);

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    try {
      const params = new URLSearchParams(search);
      params.set("cursor", cursor);
      const next = await apiGet<Schemas["TransactionPage"]>(`/transactions?${params}`);
      setItems((current) => [...current, ...next.items]);
      setCursor(next.next_cursor);
    } catch {
      toast.error("Could not load more transactions.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No transactions match these filters</EmptyTitle>
          <EmptyDescription>Try another period, or clear the filters.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <>
      <Card>
        <CardContent>
          <TransactionTable items={items} showSource onOpen={setSelected} />
        </CardContent>
      </Card>
      <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
        {/* Two counts, not "X of N": a row you edit stays in the list even when the edit moves it
            out of the filters, while the count (refreshed after the save) no longer includes it. */}
        <span>
          {items.length} shown · {initial.count} {initial.count === 1 ? "matches" : "match"} these filters
        </span>
        {cursor && (
          <Button variant="secondary" onClick={loadMore} disabled={loading}>
            {loading && <Spinner data-icon="inline-start" />}
            Load more
          </Button>
        )}
      </div>
      <TransactionPanel
        tx={selected}
        categories={categories}
        merchants={merchants}
        onClose={() => setSelected(null)}
        onSaved={(change) => setItems((rows) => applyChange(rows, change, categories))}
      />
    </>
  );
}
