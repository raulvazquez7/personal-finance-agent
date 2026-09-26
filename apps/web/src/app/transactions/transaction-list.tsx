"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TransactionTable } from "@/components/transactions/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { apiGet, type Schemas } from "@/lib/api";

type Props = { initial: Schemas["TransactionPage"]; search: string };

/** The explorer's rows, grouped by day, 100 at a time (spec 7.3). The next pages are fetched
 * by the browser with the page's own query plus the cursor. */
export function TransactionList({ initial, search }: Props) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);

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
          <TransactionTable items={items} showSource />
        </CardContent>
      </Card>
      <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
        <span>
          Showing {items.length} of {initial.count}
        </span>
        {cursor && (
          <Button variant="secondary" onClick={loadMore} disabled={loading}>
            {loading && <Spinner data-icon="inline-start" />}
            Load more
          </Button>
        )}
      </div>
    </>
  );
}
