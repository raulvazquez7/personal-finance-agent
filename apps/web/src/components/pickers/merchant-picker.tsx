"use client";

import { useState } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

/** An existing merchant (id) or a new name typed by the user (id null). */
export type MerchantChoice = { id: string | null; name: string };

type Props = {
  merchants: Schemas["MerchantOut"][];
  value: MerchantChoice | null;
  onChange: (merchant: MerchantChoice | null) => void;
  /** A label may create a merchant from a typed name; a filter only picks existing ones. */
  allowCreate?: boolean;
  showClear?: boolean;
  id?: string;
  ariaLabel?: string;
  /** The id of the field's one-line description (spec 7.2). */
  ariaDescribedBy?: string;
};

export function MerchantPicker({
  merchants,
  value,
  onChange,
  allowCreate = true,
  showClear = false,
  id,
  ariaLabel = "Merchant",
  ariaDescribedBy,
}: Props) {
  const [query, setQuery] = useState(value?.name ?? "");
  // The value can change from outside (Merge picks the suggested merchant): show its name.
  const [shownName, setShownName] = useState(value?.name);
  if (value?.name !== shownName) {
    setShownName(value?.name);
    setQuery(value?.name ?? "");
  }
  const typed = query.trim();
  const exists = merchants.some((m) => m.name.toLowerCase() === typed.toLowerCase());
  const items: MerchantChoice[] = [
    ...merchants.map((m) => ({ id: m.id, name: m.name })),
    ...(allowCreate && typed && !exists ? [{ id: null, name: typed }] : []),
  ];

  return (
    <Combobox
      items={items}
      value={value}
      // Base UI still reports the change it canceled below (Escape on a label): skip it.
      onValueChange={(merchant: MerchantChoice | null, details) => {
        if (!details.isCanceled) onChange(merchant);
      }}
      inputValue={query}
      onInputValueChange={(next, details) => {
        // A label keeps its merchant on Escape, as CategoryPicker does; a filter (with its ×) empties.
        if (details.reason === "escape-key" && !showClear) {
          details.cancel();
          details.allowPropagation();
          return;
        }
        setQuery(next);
      }}
      itemToStringLabel={(merchant: MerchantChoice) => merchant.name}
      isItemEqualToValue={(a: MerchantChoice, b: MerchantChoice) => a.id === b.id && a.name === b.name}
    >
      <ComboboxInput
        id={id}
        placeholder="Merchant"
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedBy}
        // Typing replaces the current merchant instead of adding to its name.
        onFocus={(event) => event.currentTarget.select()}
        showClear={showClear}
        className="w-full"
      />
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
