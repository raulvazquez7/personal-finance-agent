"use client";

import { useState } from "react";

import {
  Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

/** An existing merchant (id) or a new name typed by the user (id null). */
export type MerchantChoice = { id: string | null; name: string };

type Props = {
  merchants: Schemas["MerchantOut"][];
  value: MerchantChoice | null;
  onChange: (merchant: MerchantChoice | null) => void;
};

export function MerchantPicker({ merchants, value, onChange }: Props) {
  const [query, setQuery] = useState(value?.name ?? "");
  const typed = query.trim();
  const exists = merchants.some((m) => m.name.toLowerCase() === typed.toLowerCase());
  const items: MerchantChoice[] = [
    ...merchants.map((m) => ({ id: m.id, name: m.name })),
    ...(typed && !exists ? [{ id: null, name: typed }] : []),
  ];

  return (
    <Combobox
      items={items}
      value={value}
      onValueChange={(merchant: MerchantChoice | null) => onChange(merchant)}
      inputValue={query}
      onInputValueChange={setQuery}
      itemToStringLabel={(merchant: MerchantChoice) => merchant.name}
      isItemEqualToValue={(a: MerchantChoice, b: MerchantChoice) => a.id === b.id && a.name === b.name}
    >
      <ComboboxInput placeholder="Merchant" className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No merchant found.</ComboboxEmpty>
        <ComboboxList>
          {(merchant: MerchantChoice) => (
            <ComboboxItem key={merchant.id ?? `new-${merchant.name}`} value={merchant}>
              {merchant.id ? merchant.name : `Create "${merchant.name}"`}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
