"use client";

import { useState } from "react";

import { TransactionPanel } from "@/app/transactions/transaction-panel";
import type { Schemas } from "@/lib/api";
import type { LabelChange } from "@/lib/transactions";

import { TransactionTable } from "./transaction-table";

type Tx = Schemas["Transaction"];

type Props = {
  items: Tx[];
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  showSource?: boolean;
  onSaved?: (change: LabelChange) => void;
};

/** One list and the side panel for a row. Detail pages omit `onSaved`: the panel refreshes the
 * route. The explorer passes it so the rows already loaded update in place. */
export function TransactionBrowser({ items, categories, merchants, showSource, onSaved }: Props) {
  const [selected, setSelected] = useState<Tx | null>(null);
  return (
    <>
      <TransactionTable items={items} categories={categories} showSource={showSource} onOpen={setSelected} />
      <TransactionPanel
        tx={selected}
        categories={categories}
        merchants={merchants}
        onClose={() => setSelected(null)}
        onSaved={onSaved ?? (() => {})}
      />
    </>
  );
}
